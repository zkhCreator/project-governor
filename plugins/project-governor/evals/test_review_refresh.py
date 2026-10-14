"""Purpose: Regress review refresh attribution without calling a model.
Responsibilities: Verify restored candidates do not inherit stale flags and final edits still block; persist current results.
Inputs/Outputs: Frozen temporary run metadata and controlled digest changes produce the real deterministic gate outcome.
Non-goals: Does not replace independent semantic review or test iOS behavior.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from project_governor.workflow import review_existing
from project_governor.util import write_json, read_json

class ReviewRefreshTests(unittest.TestCase):
    def test_stale_flag_is_refreshed_and_end_drift_is_not_hidden(self):
        for drift in [False, True]:
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as t:
                root=Path(t);run=root/'.governance/.runs/one';change=root/'.governance/changes/feature'
                run.mkdir(parents=True);change.mkdir(parents=True)
                state={'run_id':'one','change_id':'feature','attempt':1,'candidate_digest':'a','contract_digest':'c',
                       'evidence_digest':'e','candidate_stable':False,'protected_state_stable':True,
                       'version_consistent':True,'evidence_stable':True,'pending_exceptions':[],
                       'required_reviewers':['architecture'],'automatic_checks':[], 'ui_required':False, 'reviews':{}}
                write_json(run/'run.json',state);write_json(run/'candidate-manifest.json',{'digest':'a'})
                write_json(run/'evidence-manifest.json',{'digest':'e'})
                write_json(change/'result.json',{'verdict':'blocked'})
                def inspect_review(root_arg,run_arg,passed_state,*args,**kwargs):
                    self.assertTrue(passed_state['candidate_stable'])
                    return {'architecture':{'verdict':'pass','candidate_digest':'a','contract_digest':'c','violations':[],'unverified':[]}}
                with patch('project_governor.workflow.load_project',return_value={}), \
                     patch('project_governor.workflow.load_lock',return_value={}), \
                     patch('project_governor.workflow.build_manifest',side_effect=[{'digest':'a'},{'digest':'b' if drift else 'a'}]), \
                     patch('project_governor.workflow.governance_digest',return_value='c'), \
                     patch('project_governor.workflow._directory_manifest',return_value={'digest':'e'}), \
                     patch('project_governor.workflow._run_required_reviewers',side_effect=inspect_review):
                    result=review_existing(root,'one','both')
                self.assertEqual(result['verdict'],'blocked' if drift else 'pass')
                self.assertEqual(read_json(change/'result.json')['verdict'],result['verdict'])
                self.assertEqual(read_json(run/'run.json')['candidate_stable'],not drift)
