import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from chb.arena.jobs import run_judge
from chb.arena.judge_repair import repair_issues, combined_usage
from chb.arena.machine import validate_machine
import test_judge_protocol as protocol_tests


class JudgeRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.run={'policy':{'version':'arena-machine-v1'},'revision':1}
        self.trial={'judgeExecution':{}}
        self.app=SimpleNamespace(local=Path(self.tmp.name),lock=threading.RLock(),
            db=MagicMock(),trial=lambda *_:(self.run,self.trial),event=MagicMock())
        self.control={'stop':threading.Event()};self.calls=[]
        self.bad,self.packet,self.commands=protocol_tests.JudgeProtocolTests().fixture(4)
        self.bad['ratings']['intent']['checks']['coverage']['counterEvidence']=[]
        self.good=protocol_tests.JudgeProtocolTests().fixture(3)[0]

    def attempt(self, value, *, feedback=None, tokens=10):
        index=len(self.calls)+1;self.calls.append(feedback)
        folder=self.app.local/'runs/r/t/reviews'/f'job-{index}'
        folder.mkdir(parents=True)
        self.trial['judgeExecution']['jobId']=folder.name
        raw=json.dumps(value) if isinstance(value,dict) else value
        (folder/'answer.json').write_text(raw,encoding='utf-8')
        events=[{'type':'item.completed','item':{'id':'cmd1','type':'command_execution',
            'command':self.commands[0]['command'],'aggregated_output':self.commands[0]['output'],'exit_code':0}},
            {'type':'turn.completed','usage':{'input_tokens':tokens,'cached_input_tokens':2,'output_tokens':3,'reasoning_output_tokens':1}}]
        (folder/'events.jsonl').write_text('\n'.join(map(json.dumps,events)),encoding='utf-8')
        if not isinstance(value,dict):raise ValueError('评分报告未通过校验：裁判返回的 JSON 无法解析。')
        return {**validate_machine(value,self.packet,self.commands),'jobPath':str(folder)}

    def execute(self, launch, connection_states=None, **data):
        with patch('chb.arena.jobs._run_judge_once',side_effect=launch), patch('chb.arena.judge_repair.connection_fingerprint',side_effect=connection_states or (lambda:'fixture-connection')):
            return run_judge(self.app,'r','t',{}, {},{'timeoutSeconds':600,'environment':'local',**data},self.control)

    def test_reviewer_receives_missing_counter_and_supplies_its_own_lower_grade(self):
        budgets=[]
        def launch(*args,feedback=None,deadline=None):
            budgets.append(args[5]['timeoutSeconds'])
            if not self.calls:return self.attempt(self.bad)
            self.assertEqual(feedback['issues'][0]['dimension'],'intent')
            self.assertEqual(feedback['issues'][0]['facet'],'coverage')
            self.assertEqual(feedback['commands'][0]['output'],self.commands[0]['output'])
            return self.attempt(self.good,feedback=feedback,tokens=7)
        result=self.execute(launch)
        self.assertEqual(result['ratings']['intent']['score'],75)
        self.assertEqual(len(self.calls),2);self.assertLessEqual(budgets[1],budgets[0])
        self.assertEqual(result['judgeUsage']['inputTokens'],17)
        self.assertEqual(result['automaticRepair']['status'],'completed')
        saved=json.loads((self.app.local/'runs/r/t/reviews/job-1/answer.json').read_text())
        self.assertEqual(saved,self.bad)  # No developer/platform grade edit.

    def test_valid_zero_grade_is_not_retried_or_replaced(self):
        zero=protocol_tests.JudgeProtocolTests().fixture(0)[0]
        result=self.execute(lambda *_,feedback=None,deadline=None:self.attempt(zero))
        self.assertEqual(result['ratings']['intent']['score'],0);self.assertEqual(len(self.calls),1)

    def test_bounded_feedback_keeps_unknown_if_reviewer_never_supplies_evidence(self):
        result=self.execute(lambda *_,feedback=None,deadline=None:self.attempt(self.bad,feedback=feedback))
        self.assertEqual(len(self.calls),3);self.assertIsNone(result['ratings']['intent']['score'])
        self.assertEqual(result['automaticRepair']['status'],'partial')

    def test_budget_is_shared_and_does_not_restart_for_feedback(self):
        clock=[0]
        def launch(*_,feedback=None,deadline=None):
            result=self.attempt(self.bad);clock[0]=550;return result
        with patch('chb.arena.jobs.time.monotonic',side_effect=lambda:clock[0]):result=self.execute(launch)
        self.assertEqual(len(self.calls),1);self.assertIsNone(result['ratings']['intent']['score'])
        self.assertIn('剩余时间',result['automaticRepair']['note'])

    def test_invalid_json_is_feedback_data_and_can_be_repaired_by_reviewer(self):
        def launch(*_,feedback=None,deadline=None):
            if not self.calls:return self.attempt('{invalid-json')
            self.assertEqual(feedback['answer'],'{invalid-json')
            return self.attempt(self.good,feedback=feedback)
        self.assertEqual(self.execute(launch)['ratings']['intent']['score'],75)

    def test_environment_block_does_not_cause_an_extra_model_call(self):
        with self.assertRaisesRegex(ValueError,'额度不足'):
            self.execute(lambda *_,**__:(_ for _ in ()).throw(ValueError('裁判模型额度不足')))
        result=validate_machine(self.bad,self.packet,self.commands)
        for row in result['ratings']['intent']['checks'].values():row.update(score=None,reason='环境不可用')
        result['ratings']['intent']['score']=None
        self.assertEqual(repair_issues(result),[])

    def test_cancel_does_not_start_feedback_model(self):
        def launch(*_,feedback=None,deadline=None):
            result=self.attempt(self.bad);self.control['stop'].set();return result
        with self.assertRaisesRegex(ValueError,'取消'):self.execute(launch)
        self.assertEqual(len(self.calls),1)

    def test_missing_usage_is_unknown_not_partial_cost_total(self):
        self.assertIsNone(combined_usage([{'usage':None},{'usage':{'inputTokens':10}}]))

    def test_account_change_stops_feedback_instead_of_switching_account(self):
        result=self.execute(lambda *_,**__:self.attempt(self.bad),connection_states=['first','changed'])
        self.assertEqual(len(self.calls),1);self.assertIn('换号',result['automaticRepair']['note'])
        self.assertIsNone(result['ratings']['intent']['score'])

    def test_feedback_budget_failure_keeps_first_verified_observations(self):
        from chb.arena.review_options import ReviewBudgetExceeded
        def launch(*_,**__):
            if not self.calls:return self.attempt(self.bad)
            raise ReviewBudgetExceeded('审查时间预算已用完')
        result=self.execute(launch)
        self.assertEqual(result['ratings']['intent']['checks']['quality']['score'],100)
        self.assertIsNone(result['ratings']['intent']['score'])
        self.assertEqual(result['automaticRepair']['status'],'partial')
        self.assertEqual(result['judgeUsage']['inputTokens'],10)
        self.assertIsNone(result['automaticRepair']['attempts'][1]['jobId'])

    def test_recovery_can_reduce_remaining_calls_but_not_increase_the_fixed_limit(self):
        from chb.arena.judge_repair import attempt_limit
        result=self.execute(lambda *_,feedback=None,deadline=None:self.attempt(self.bad,feedback=feedback),maxReviewAttempts=2)
        self.assertEqual(len(self.calls),2)
        self.assertEqual(result['automaticRepair']['maxAttempts'],2)
        for invalid in (0,4,True,'2',None):
            with self.subTest(value=invalid),self.assertRaises(ValueError):attempt_limit({'maxReviewAttempts':invalid})


if __name__=='__main__':unittest.main()
