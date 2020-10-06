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
from gerrit import upload_all_comments, get_gerrit_rest_api, Gerrit
from git import GerritGit
from message_dao import MessageDao
from patch_parser import map_comments_to_gerrit, parse_comments, Patch, Patchset
from setup_gmail import Message
from typing import List, Set

EPOCH_HASH = 'cc49e216e3fdff0ffed7675dc7215aba5e3d05cc'
GIT_PATH = '../linux-kselftest/git/0.git'
FILE_DIR = 'index_files'

def remove_files(file_dir : str):
    files = glob.glob(f'{file_dir}/*')
    for f in files:
        os.remove(f)

def main():
    gerrit_url = 'https://linux-review.googlesource.com'
    gob_url = 'http://linux.googlesource.com'
    rest = get_gerrit_rest_api('gerritcookies', gerrit_url)
    gerrit = Gerrit(rest)
    gerrit_git = GerritGit(git_dir='gerrit_git_dir',
                           cookie_jar_path='gerritcookies',
                           url=gob_url, project='linux/kernel/git/torvalds/linux', branch='master')
    message_dao = MessageDao()
    archive_index = ArchiveMessageIndex(message_dao)
    last_hash : str
    # Check if database is populated
    if(archive_index.size() == 0):
        last_hash = fill_message_directory(GIT_PATH, FILE_DIR, EPOCH_HASH)
        # The uploading only starts when the server loop starts.
        # O/w there could be 10'000s of emails uploaded to Gerrit all at once.
        archive_index.update(FILE_DIR) 
        remove_files(FILE_DIR)
    else:
        last_hash = message_dao.get_lash_hash()
    
    # Start the main server loop
    while(True):
        lash_hash = fill_message_directory(GIT_PATH, FILE_DIR, last_hash)
        new_messages = archive_index.update(FILE_DIR)
        
        # Differentiate between messages to upload and comments
        messages_to_upload : List[str] = []
        messages_with_new_comments : Set[str] = set()
        parent_patches : Set[str] = set()
        replies : List[Message] = []
        
        # First separate between parents and replies. All parents of patchsets will be uploaded
        for message in new_messages:
            if not message.in_reply_to:
                parent_patches.add(message.id)
                messages_to_upload.append(message.id)
                continue
            replies.append(message)
        
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
                email_thread = archive_index.find(message_id)
                patchset = parse_comments(email_thread)
                gerrit_git.apply_patchset_and_cleanup(patchset)
                find_and_label_all_revision_ids(gerrit, patchset)
                upload_all_comments(gerrit, patchset)
            except ValueError:
                print(f'Failed to find {message_id} in index.')
                pass
            
        for message_id in messages_with_new_comments:
            try:
                email_thread = archive_index.find(message_id)
                patchset = parse_comments(email_thread)
                upload_all_comments(gerrit, patchset)
            except ValueError:
                print(f'Failed to find {message_id} in index.')
                pass
        
        # Clean up directory for next loop
        remove_files(FILE_DIR)
        time.sleep(10)
        
        
    
    

if __name__ == '__main__':
    main()
