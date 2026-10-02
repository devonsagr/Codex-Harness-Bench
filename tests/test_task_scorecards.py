import unittest
from chb.arena.task_scorecards import CARDS, PROJECT_POLICY_VERSION, AUTO_PROJECT_VERSION, score_public, score_project, score_project_policy, score_project_auto, score_progress
from chb.arena.scoring import AUTO_MACHINE_POLICY, AUTO_PROJECT_GROUPS, auto_dimensions, policy


class PublicScorecardTests(unittest.TestCase):
    def test_failed_public_result_has_known_contribution_without_ai_quality(self):
        task={'publicSource':{'id':'anko-default-function-arguments'}}
        native={'id':'n','reward':0,'f2p_total':2,'f2p_passed':1,'p2p_total':100,'p2p_passed':100,
                'f2pCases':[{'name':'[f2p] TestLoadDefaultArguments','status':'passed'},
                            {'name':'[f2p] TestDefaultArgumentsVisible','status':'failed'}]}
        card=score_public(task,native,None,None);progress=score_progress(card)
        self.assertIsNone(card['overall']);self.assertEqual(native['reward'],0)
        self.assertEqual((progress['knownPoints'],progress['minimum'],progress['maximum'],progress['coverage']),(55,55,65,90))
        self.assertEqual([row['label'] for row in progress['rows'] if row['points'] is None],['工程可维护性'])

    def test_partial_auto_group_keeps_known_dimensions_and_fixed_denominator(self):
        task={'taskFamily':'web-interface','hasFrontendUI':True,'checks':[]}
        trial={'captures':[{'checks':[]}]}
        scores={key:75 for key in auto_dimensions(task)};scores['robustness']=None
        card=score_project_auto(task,trial,scores,'review');progress=score_progress(card)
        self.assertIsNone(card['overall']);self.assertIsNone(card['items'][1]['points'])
        self.assertEqual((progress['minimum'],progress['maximum'],progress['coverage']),(71.25,76.25,95))
        self.assertEqual(progress['rows'][0]['points'],33.75)
        scores['robustness']=75;scores['instruction']=None
        progress=score_progress(score_project_auto(task,trial,scores,'review'))
        self.assertEqual((progress['minimum'],progress['maximum'],progress['coverage']),(67.5,77.5,90))

    def test_failed_checks_are_known_zero_but_missing_checks_are_unknown(self):
        task={'taskFamily':'swe-feature','hasFrontendUI':False,'checks':[{'id':'check'}]}
        scores={key:100 for key in auto_dimensions(task)}
        card=score_project_auto(task,{'captures':[{'checks':[]}]},scores,'review')
        progress=score_progress(card)
        self.assertEqual((progress['minimum'],progress['maximum'],progress['coverage']),(90,100,90))
        failed=score_project_auto(task,{'captures':[{'checks':[{'status':'failed'}]}]},scores,'review')
        self.assertEqual(failed['overall'],90)
        progress=score_progress(failed)
        self.assertEqual((progress['minimum'],progress['maximum'],progress['coverage']),(90,90,100))

    def test_all_zero_observations_are_complete_and_no_card_is_unknown(self):
        task={'taskFamily':'swe-feature','hasFrontendUI':False,'checks':[]}
        card=score_project_auto(task,{'captures':[{'checks':[]}]},{key:0 for key in auto_dimensions(task)},'review')
        self.assertEqual(card['overall'],0)
        progress=score_progress(card)
        self.assertEqual((progress['minimum'],progress['maximum'],progress['unknownWeight'],progress['coverage']),(0,0,0,100))
        self.assertIsNone(score_progress(None))

    def test_custom_progress_uses_frozen_normalized_weights_without_filling_gaps(self):
        task={'hasFrontendUI':False,'checks':[]}
        policy={'dimensions':{'intent':2,'robustness':1},'rubrics':{'intent':{'label':'目标'},'robustness':{'label':'边界'}}}
        card=score_project_policy(task,{'captures':[{'checks':[]}]},{'intent':60,'robustness':None},'r',policy)
        progress=score_progress(card)
        self.assertIsNone(card['overall'])
        self.assertEqual(progress['knownPoints'],40)
        self.assertEqual(progress['unknownWeight'],33.33)
        self.assertEqual(progress['maximum'],73.33)

    def test_old_card_range_respects_its_group_rounding_and_one_decimal_total(self):
        scores={'intent':83.33,'instruction':None,'verification':75,'robustness':66.67,
                'maintainability':91.67,'handoff':58.33}
        task={'hasFrontendUI':False,'checks':[]};trial={'captures':[{'checks':[]}]}
        progress=score_progress(score_project(task,trial,scores,'r'))
        self.assertEqual(progress['minimum'],score_project(task,trial,{**scores,'instruction':0},'r')['overall'])
        self.assertEqual(progress['maximum'],score_project(task,trial,{**scores,'instruction':100},'r')['overall'])

    def test_anko_failure_keeps_core_failure_visible(self):
        task = {'publicSource': {'id': 'anko-default-function-arguments'}}
        native = {'id': 'native-1', 'reward': 0, 'f2p_total': 2, 'f2p_passed': 1, 'p2p_total': 119, 'p2p_passed': 119,
                  'f2pCases': [{'name': '[f2p] github.com/mattn/anko/core.TestLoadDefaultArguments', 'status': 'passed'},
                               {'name': '[f2p] github.com/mattn/anko/vm.TestDefaultArgumentsVisible', 'status': 'failed'}]}
        card = score_public(task, native, 68, 'review-1')
        self.assertEqual(card['overall'], 61.8)
        self.assertEqual([row['points'] for row in card['items']], [35, 0, 20, 6.8])
        self.assertEqual(native['reward'], 0)

    def test_missing_case_or_quality_evidence_does_not_invent_total(self):
        task = {'publicSource': {'id': 'anko-default-function-arguments'}}
        native = {'id': 'native-1', 'reward': 1, 'f2p_total': 2, 'f2p_passed': 2, 'p2p_total': 2, 'p2p_passed': 2,
                  'f2pCases': [{'name': 'unmapped', 'status': 'passed'}]}
        self.assertIsNone(score_public(task, native, 80, 'review-1')['overall'])
        native['f2pCases'] = [{'name': '[f2p] TestLoadDefaultArguments', 'status': 'passed'},
                              {'name': '[f2p] TestDefaultArgumentsVisible', 'status': 'passed'}]
        self.assertIsNone(score_public(task, native, None, None)['overall'])
        native['p2p_passed'] = 1
        self.assertEqual(score_public(task, native, 80, 'review-1')['overall'], 78)
        native.pop('p2p_passed')
        self.assertIsNone(score_public(task, native, 80, 'review-1')['overall'])
        native['p2p_passed'] = 2
        native['f2pCases'][1] = native['f2pCases'][0]
        self.assertIsNone(score_public(task, native, 80, 'review-1')['overall'])

    def test_cards_have_one_hundred_points_and_no_generic_public_fallback(self):
        self.assertTrue(all(sum(weight for _, weight, _ in groups) == 70 for _, groups in CARDS.values()))
        self.assertIsNone(score_public({'publicSource': {'id': 'unknown'}}, {'id': 'n'}, 90, 'r'))

    def test_open_project_card_uses_applicable_ui_and_hard_check(self):
        scores = {'intent': 80, 'instruction': 90, 'verification': 95, 'robustness': 70,
                  'ux': 60, 'maintainability': 80, 'handoff': 90}
        trial = {'state': 'completed', 'captures': [{'checks': [{'status': 'passed'}]}]}
        task = {'hasFrontendUI': True, 'checks': [{'id': 'browser'}]}
        card = score_project(task, trial, scores, 'review-1')
        self.assertEqual([item['weight'] for item in card['items']], [60, 25, 15])
        self.assertEqual(card['overall'], 80.5)
        self.assertEqual(score_project(task, {**trial, 'state': 'captured'}, scores, 'review-1')['overall'], 80.5)
        self.assertIsNone(score_project(task, trial, scores, None)['overall'])
        trial['captures'][0]['checks'][0]['status'] = 'failed'
        failed = score_project(task, trial, scores, 'review-1')
        self.assertEqual(failed['overall'], 71)
        trial['captures'][0]['checks'] = []
        self.assertIsNone(score_project(task, trial, scores, 'review-1')['overall'])

    def test_non_web_project_does_not_require_visual_grade(self):
        trial = {'state': 'completed', 'captures': [{'checks': []}]}
        task = {'hasFrontendUI': False, 'checks': []}
        scores = {'intent': 80, 'instruction': 90, 'verification': 70, 'robustness': 60,
                  'maintainability': 85, 'handoff': 90}
        self.assertEqual(score_project(task, trial, scores, 'review-1')['overall'], 78)

    def test_new_open_project_card_uses_frozen_selected_weights_and_check_limits(self):
        task = {'hasFrontendUI': True, 'checks': [{'id': 'browser'}]}
        trial = {'state': 'completed', 'captures': [{'checks': [{'status': 'passed'}]}]}
        scores = {'intent': 90, 'visual': 70, 'verification': 80}
        policy = {'dimensions': {'intent': 50, 'visual': 30, 'verification': 20},
                  'rubrics': {key: {'label': key} for key in scores}}
        card = score_project_policy(task, trial, scores, 'review-1', policy)
        self.assertEqual(card['version'], PROJECT_POLICY_VERSION)
        self.assertEqual(card['overall'], 82)
        self.assertEqual(score_project_policy(task, {**trial, 'state': 'captured'}, scores, 'review-1', policy)['overall'], 82)
        self.assertEqual([item['key'] for item in card['items']], list(scores))
        self.assertEqual([item['points'] for item in card['items']], [45, 21, 16])
        policy['dimensions'] = {'intent': 20, 'visual': 60, 'verification': 20}
        self.assertEqual(score_project_policy(task, trial, scores, 'review-1', policy)['overall'], 76)
        trial['captures'][0]['checks'][0]['status'] = 'failed'
        failed = score_project_policy(task, trial, scores, 'review-1', policy)
        self.assertEqual(failed['overall'], 60)
        self.assertEqual(failed['items'][-1]['ratio'], 0)
        self.assertIn('程序检查失败', failed['items'][-1]['evidence'])
        trial['captures'][0]['checks'] = []
        self.assertIsNone(score_project_policy(task, trial, scores, 'review-1', policy)['overall'])

    def test_new_non_web_card_excludes_visual_weights(self):
        task = {'hasFrontendUI': False, 'checks': []}
        trial = {'state': 'completed', 'captures': [{'checks': []}]}
        policy = {'dimensions': {'intent': 50, 'visual': 50},
                  'rubrics': {'intent': {'label': '需求'}, 'visual': {'label': '视觉'}}}
        card = score_project_policy(task, trial, {'intent': 83}, 'review-1', policy)
        self.assertEqual(card['overall'], 83)
        self.assertEqual([item['key'] for item in card['items']], ['intent'])

    def test_auto_profiles_choose_distinct_task_evidence_and_total_one_hundred(self):
        self.assertEqual(sum(AUTO_MACHINE_POLICY['dimensions'].values()), 100)
        self.assertTrue(policy(AUTO_MACHINE_POLICY)['taskTypeAuto'])
        for groups in AUTO_PROJECT_GROUPS.values():
            self.assertEqual([sum(points for _, points in rows) for _, rows in groups], [60, 25, 15])
            keys = [key for _, rows in groups for key, _ in rows]
            self.assertEqual(len(keys), len(set(keys)))
        web = auto_dimensions({'taskFamily': 'web-interface', 'hasFrontendUI': True})
        coding = auto_dimensions({'taskFamily': 'swe-feature', 'hasFrontendUI': False})
        public = auto_dimensions({'publicSource': {'id': 'fixture'}})
        self.assertEqual(web['visual'], 5)
        self.assertEqual(web['reasoning'], 5)
        self.assertNotIn('reasoning',auto_dimensions({'taskFamily':'web-interface','hasFrontendUI':True},'project-tasktype-v2'))
        self.assertNotIn('visual', coding)
        self.assertEqual(public, {'maintainability': 100})
        modified = {**AUTO_MACHINE_POLICY, 'dimensions': {**AUTO_MACHINE_POLICY['dimensions'], 'visual': 3, 'intent': 34}}
        with self.assertRaisesRegex(ValueError, '自动题型评分方案不能修改'):
            policy(modified)

    def test_auto_web_card_has_60_25_15_groups_and_limited_check_evidence(self):
        task = {'taskFamily': 'web-interface', 'hasFrontendUI': True, 'checks': [{'id': 'browser'}]}
        trial = {'state': 'completed', 'captures': [{'checks': [{'status': 'passed'}]}]}
        scores = {'intent': 80, 'instruction': 90, 'reasoning': 60, 'ux': 70, 'visual': 60,
                  'verification': 100, 'robustness': 80, 'maintainability': 85, 'handoff': 90}
        card = score_project_auto(task, trial, scores, 'review-1')
        self.assertEqual(card['version'], AUTO_PROJECT_VERSION)
        self.assertEqual([item['weight'] for item in card['items']], [60, 25, 15])
        self.assertEqual([item['points'] for item in card['items']], [48, 19, 13])
        self.assertEqual(card['overall'], 80)
        self.assertEqual(score_project_auto(task, {**trial, 'state': 'captured'}, scores, 'review-1')['overall'], 80)
        old=score_project_auto(task,trial,scores,'review-1','project-tasktype-v2')
        self.assertEqual(old['version'],'project-tasktype-v2')
        self.assertEqual(old['overall'],81)
        trial['captures'][0]['checks'][0]['status'] = 'failed'
        self.assertEqual(score_project_auto(task, trial, scores, 'review-1')['overall'], 75)
        trial['captures'][0]['checks'][0]['status'] = 'error'
        self.assertIsNone(score_project_auto(task, trial, scores, 'review-1')['overall'])
        trial['captures'][0]['checks'][0]['status'] = 'passed'
        del scores['visual']
        self.assertIsNone(score_project_auto(task, trial, scores, 'review-1')['overall'])

    def test_auto_collaboration_uses_process_evidence_without_web_items(self):
        task = {'taskFamily': 'collaboration-planning', 'hasFrontendUI': False, 'checks': []}
        scores = {'intent': 90, 'instruction': 70, 'reasoning': 80, 'requirements': 60,
                  'communication': 75, 'maintainability': 85, 'handoff': 95}
        card = score_project_auto(task, {'state': 'completed', 'captures': []}, scores, 'review-2')
        self.assertEqual(card['overall'], 83)
        self.assertNotIn('ux', auto_dimensions(task))


if __name__ == '__main__':
    unittest.main()
