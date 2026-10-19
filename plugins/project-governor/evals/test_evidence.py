"""Purpose: Verify supplemental evidence isolation and byte integrity.
Responsibilities: Cover successful copies, explicit provenance, missing files, path escape, symlinks and expected hashes.
Inputs/Outputs: Disposable files and manifests produce copied bytes or blocked errors.
Non-goals: Does not simulate reviewer judgment or certify performance.
Key Decisions: Each case uses an isolated temporary project so path and symlink rejection exercise the real importer.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from project_governor.evidence import import_evidence
from project_governor.errors import GovernanceError

class SupplementalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        (self.root/'evidence').mkdir(); (self.root/'evidence/result.txt').write_text('actual result')
        self.manifest = self.root/'evidence/import.json'
    def tearDown(self): self.temp.cleanup()
    def run_import(self, path='evidence/result.txt', **extra):
        self.manifest.write_text(json.dumps({'schema_version':1,'artifacts':[{'path':path,'description':'Captured test output',**extra}]}))
        return import_evidence(self.root,self.manifest,self.root/'run')
    def test_copy_preserves_bytes_and_does_not_certify_provenance(self):
        result=self.run_import(provenance={'revision':'caller claim'})
        item=result['artifacts'][0]
        self.assertEqual((self.root/'run'/item['path']).read_text(),'actual result')
        self.assertFalse(item['provenance_verified_by_import'])
        self.assertEqual(item['provided_provenance'],{'revision':'caller claim'})
    def test_missing_artifact_blocks(self):
        with self.assertRaises(GovernanceError):self.run_import('evidence/missing')
    def test_outside_evidence_blocks(self):
        (self.root/'private.txt').write_text('not allowed')
        with self.assertRaises(GovernanceError):self.run_import('private.txt')
    def test_symlink_blocks(self):
        (self.root/'evidence/link').symlink_to(self.root/'evidence/result.txt')
        with self.assertRaises(GovernanceError):self.run_import('evidence/link')
    def test_nested_symlink_blocks(self):
        (self.root/'evidence/folder').mkdir()
        (self.root/'evidence/folder/link').symlink_to(self.root/'evidence/result.txt')
        with self.assertRaises(GovernanceError):self.run_import('evidence/folder')
    def test_wrong_expected_digest_blocks(self):
        with self.assertRaises(GovernanceError):self.run_import(digest='0'*64)
    def test_directory_keeps_nested_paths(self):
        (self.root/'evidence/folder/sub').mkdir(parents=True)
        (self.root/'evidence/folder/sub/capture.txt').write_text('capture')
        result=self.run_import('evidence/folder')
        self.assertEqual((self.root/'run'/result['artifacts'][0]['path']/'sub/capture.txt').read_text(),'capture')
    def test_no_manifest_preserves_existing_behavior(self):
        self.assertEqual(import_evidence(self.root,None,self.root/'run'),{'artifacts':[]})

    def test_source_cannot_contain_copy_destination(self):
        (self.root/'evidence/results').mkdir()
        (self.root/'evidence/results/test.txt').write_text('data')
        self.manifest.write_text(json.dumps({'schema_version':1,'artifacts':[
            {'path':'evidence/results','description':'would recursively contain the run'}]}))
        with self.assertRaises(GovernanceError):
            import_evidence(self.root,self.manifest,self.root/'evidence/results/run')
