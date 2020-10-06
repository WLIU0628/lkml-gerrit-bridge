# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import glob
import time

from archive_converter import ArchiveMessageIndex
from archive_updater import fill_message_directory
from gerrit import upload_all_comments, get_gerrit_rest_api, Gerrit, find_and_label_all_revision_ids
from git import GerritGit
from message_dao import MessageDao
from patch_parser import map_comments_to_gerrit, parse_comments, Patch, Patchset
from setup_gmail import Message
from typing import List, Set, Tuple

EPOCH_HASH = 'cc49e216e3fdff0ffed7675dc7215aba5e3d05cc'
GIT_PATH = '../linux-kselftest/git/0.git'
FILE_DIR = 'index_files'
GERRIT_URL = 'https://linux-review.googlesource.com'
GOB_URL = 'http://linux.googlesource.com'
COOKIE_JAR_PATH = 'gerritcookies'
WAIT_TIME = 10

class Server(object):
    def __init__(self):
        rest = get_gerrit_rest_api(COOKIE_JAR_PATH, GERRIT_URL)
        self.gerrit = Gerrit(rest)
        self.gerrit_git = GerritGit(git_dir='gerrit_git_dir',
                               cookie_jar_path=COOKIE_JAR_PATH,
                               url=GOB_URL, project='linux/kernel/git/torvalds/linux', branch='master')
        message_dao = MessageDao()
        self.archive_index = ArchiveMessageIndex(message_dao)
        self.last_hash : str
        # Check if database is populated
        if(self.archive_index.size() == 0):
            self.last_hash = fill_message_directory(GIT_PATH, FILE_DIR, EPOCH_HASH)
            messages = self.archive_index.update(FILE_DIR) 
            messages_to_upload, _ = self.split_parent_and_reply_messages(messages) # Only uploading parents
            for message in messages_to_upload:
                try:
                    email_thread = self.archive_index.find(message.id)
                    patchset = parse_comments(email_thread)
                    self.gerrit_git.apply_patchset_and_cleanup(patchset)
                    find_and_label_all_revision_ids(self.gerrit, patchset)
                    upload_all_comments(self.gerrit, patchset)
                except ValueError:
                    print(f'Failed to find {message.id} in index.')
                    pass
                except:
                    print('Failed because of an unexpected error.')
                    pass
            self.remove_files(FILE_DIR)
        else:
            self.last_hash = message_dao.get_lash_hash()
    
    @staticmethod
    def remove_files(file_dir : str):
        files = glob.glob(f'{file_dir}/*')
        for f in files:
            os.remove(f)
    
    # returns parents, then replies as lists
    @staticmethod
    def split_parent_and_reply_messages(messages : List[Message]) -> Tuple[List[Message], List[Message]]:
        parents : List[Message] = []
        replies : List[Message] = []
        for message in messages:
                if not message.in_reply_to:
                    parents.append(message)
                    continue
                replies.append(message)
        return (parents, replies)
    
    def run(self):
        while(True):
            self.update_convert_upload()
            time.sleep(WAIT_TIME)
    
    def update_convert_upload(self):
        self.lash_hash = fill_message_directory(GIT_PATH, FILE_DIR, self.last_hash)
        new_messages = self.archive_index.update(FILE_DIR)

        # Differentiate between messages to upload and comments
        messages_to_upload : List[str] = []
        messages_with_new_comments : Set[str] = set()
        parent_patches : Set[str] = set()
        parents, replies = self.split_parent_and_reply_messages(new_messages)
        
        # First separate between parents and replies. All parents of patchsets will be uploaded
        for message in parents:
            parent_patches.add(message.id)
            messages_to_upload.append(message.id)
        
        # Determine which of the replies should be uploaded
        for message in replies:
            if message.in_reply_to in parent_patches:
                continue
            
            # Reply is a patch to be uploaded (as the parent of patchset is not in new_messages)
            if message.is_patch():
                messages_to_upload.append(message.id)
            # Reply is a comment that's parent is not in this batch of messages. It's parent's comments should be reuploaded
            else:
                messages_with_new_comments.add(message.in_reply_to)
                
        # Start uploading files
        for message_id in messages_to_upload:
            try:
                print(message_id)
                email_thread = self.archive_index.find(message_id)
                patchset = parse_comments(email_thread)
                self.gerrit_git.apply_patchset_and_cleanup(patchset)
                find_and_label_all_revision_ids(self.gerrit, patchset)
                upload_all_comments(self.gerrit, patchset)
            except ValueError:
                print(f'Failed to find {message_id} in index.')
                pass
            except:
                print('Failed because of an unexpected error. In loop.')
                pass
            
        for message_id in messages_with_new_comments:
            try:
                email_thread = self.archive_index.find(message_id)
                patchset = parse_comments(email_thread)
                upload_all_comments(self.gerrit, patchset)
            except ValueError:
                print(f'Failed to find {message_id} in index.')
                pass
            except:
                print('Failed because of an unexpected error. Comments')
                pass
        
        # Clean up directory for next loop
        self.remove_files(FILE_DIR)

def main():
    server = Server()
    server.run()
    

        
        
        
    
    

if __name__ == '__main__':
    main()
