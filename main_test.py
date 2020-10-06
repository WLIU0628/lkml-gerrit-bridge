import unittest
import os
import tempfile
import shutil
from unittest import mock
from typing import List
import archive_updater
import gerrit
import git

from archive_converter import ArchiveMessageIndex
from main import Server
from message_dao import MessageDao
from patch_parser import parse_comments
from setup_gmail import Message


class MainTest(unittest.TestCase):

    def test_remove_files(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.assertEqual(len(os.listdir(self.tmp_dir)), 0)
        file = os.path.join(self.tmp_dir, 'file_to_be_removed.txt')
        with open(file, 'w') as f:
            f.write('this file will be removed')
        self.assertEqual(len(os.listdir(self.tmp_dir)), 1)
        Server.remove_files(self.tmp_dir)
        self.assertEqual(len(os.listdir(self.tmp_dir)), 0)
        shutil.rmtree(self.tmp_dir)
    
    def test_split_parent_and_reply_messages(self):
        archive_index = ArchiveMessageIndex(MessageDao())
        messages = archive_index.update('test_data')
        parents, replies = Server.split_parent_and_reply_messages(messages)
        self.assertEqual(len(parents), 2)
        self.assertEqual(len(replies), 6)
        
        expected_parents = ['[PATCH v2 1/2] Input: i8042 - Prevent intermixing i8042 commands',
                    '[PATCH v2 0/4] kselftests/arm64: add PAuth tests']
        expected_replies = ['Re: [PATCH] Remove final reference to superfluous smp_commence().',
                    '[PATCH v2 1/3] dmaengine: add dma_get_channel_caps()',
                    '[PATCH v2 1/4] kselftests/arm64: add a basic Pointer Authentication test',
                    '[PATCH v2 2/4] kselftests/arm64: add nop checks for PAuth tests',
                    '[PATCH v2 3/4] kselftests/arm64: add PAuth test for whether exec() changes keys',
                    '[PATCH v2 4/4] kselftests/arm64: add PAuth tests for single threaded consistency and key uniqueness']
        
        def compare_message_subject(messages : List[Message], subjects : List[str]):
            for message, subject in zip(messages,subjects):
                self.assertEqual(message.subject, subject)
        compare_message_subject(parents, expected_parents)
        compare_message_subject(replies, expected_replies)
    
    @mock.patch.object(archive_updater, 'fill_message_directory')
    @mock.patch.object(git, 'GerritGit')
    @mock.patch.object(gerrit, 'find_and_label_all_revision_ids')
    @mock.patch.object(gerrit, 'upload_all_comments')
    def test_server_upload_across_batches(self, mock_gerrit_upload, mock_gerrit_find,
                                        mock_apply_patchset, mock_fill_message_directory):
        archive_index = ArchiveMessageIndex(MessageDao())
        messages = archive_index.update('test_data')
        first_batch = messages[0:6]
        second_batch = messages[6:]
        mock_fill_message_directory.return_value = ''
        
       
        # declaring mock objects here because I want to use the ArchiveMessageIndex functionality to build the test data
        with mock.patch.object(ArchiveMessageIndex, 'update') as mock_update, mock.patch.object(ArchiveMessageIndex, 'find') as mock_find:
            mock_update.side_effect = [first_batch, second_batch]
            mock_find.side_effect = [messages[2], messages[3], messages[6], messages[7]]
            server = Server()
            self.assertEqual(mock_apply_patchset.apply_patchset_and_cleanup.call_count, 2)
            self.assertEqual(mock_gerrit_find.call_count, 2)
            self.assertEqual(mcok_gerrit_upload.call_count, 2)
            
            server.update_convert_upload()
            self.assertEqual(mock_apply_patchset.apply_patchset_and_cleanup.call_count, 4)
            self.assertEqual(mock_gerrit_find.call_count, 4)
            self.assertEqual(mcok_gerrit_upload.call_count, 4)
        
       
        
        
    


if __name__ == '__main__':
    unittest.main()