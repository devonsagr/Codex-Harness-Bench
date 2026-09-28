import copy
import unittest
from chb.arena.judge_reliability import summarize, comparison_key


class JudgeReliabilityTests(unittest.TestCase):
    def row(self, id_='a', value=95):
        return {'id':id_,'jobPath':'/job/'+id_,'captureId':'c','evidenceKey':'e','model':'gpt-6-luna',
                'reasoningEffort':'max','judgePromptSha256':'prompt','judgePacketSha256':'packet',
                'reviewEnvironment':'docker','imageId':'image','codexVersion':'fixture','serviceTier':'standard',
                'scoreSchema':'arena-machine-v1','ratings':{'intent':{'score':value}}}

    def test_one_high_score_is_not_calibration(self):
        r=summarize({'reviews':[self.row()]},{'machineReviewId':'a'})
        self.assertEqual(r['status'],'single-run');self.assertFalse(r['calibrated']);self.assertEqual(r['ranges'],[])

    def test_repeat_spread_is_empirical_not_margin_of_error(self):
        r=summarize({'reviews':[self.row(),self.row('b',70)]},{'machineReviewId':'b'})
        self.assertEqual(r['sameProtocolRuns'],2)
        self.assertEqual(r['ranges'][0],{'dimension':'intent','samples':2,'min':70,'max':95,'spread':25})
        self.assertFalse(r['calibrated'])

    def test_different_judges_prompts_packets_and_snapshots_not_pooled(self):
        for key in ['model','reasoningEffort','judgePromptSha256','judgePacketSha256','captureId','evidenceKey','imageId','serviceTier']:
            b=self.row('b',70);b[key]='different'
            r=summarize({'reviews':[self.row(),b]},{'machineReviewId':'a'})
            self.assertEqual(r['sameProtocolRuns'],1,key)

    def test_reparse_and_duplicate_job_do_not_inflate_repeat_count(self):
        a=self.row();b=self.row('b');b['jobPath']=a['jobPath'];c=self.row('c');c['revalidatedFrom']='b'
        r=summarize({'reviews':[a,b,c]},{'machineReviewId':'c'})
        self.assertEqual(r['sameProtocolRuns'],1)

    def test_old_unknown_protocol_is_not_equal_protocol(self):
        a=self.row();a.pop('judgePacketSha256')
        r=summarize({'reviews':[a]},{'machineReviewId':'a'})
        self.assertEqual(r['status'],'unmeasured');self.assertIn('judgePacketSha256',r['missingProtocol'])

    def test_null_scores_not_counted_as_zero(self):
        r=summarize({'reviews':[self.row(),self.row('b',None)]},{'machineReviewId':'b'})
        self.assertEqual(r['sameProtocolRuns'],2);self.assertEqual(r['ranges'],[])

    def test_new_comparison_key_excludes_check_measurements_not_contract(self):
        packet={'task':{'id':'t','prompt':'frozen'},'policy':{'dimensions':{'intent':100}},
                'manifestHash':'frozen','evaluationScope':{'kind':'final'},
                'checks':[{'id':'c','imageId':'image','argv':['test'],'at':'a','seconds':1,'status':'passed'}]}
        a=comparison_key(packet);packet['checks'][0].update(at='b',seconds=2,status='failed')
        self.assertEqual(a,comparison_key(packet))
        x=self.row();y=self.row('b',70)
        x['judgeComparisonKey']=y['judgeComparisonKey']=a
        y.update(judgePacketSha256='new-observation',evidenceKey='new-check-time')
        self.assertEqual(summarize({'reviews':[x,y]},{'machineReviewId':'b'})['sameProtocolRuns'],2)
        packet['policy']['dimensions']={'intent':80,'ux':20}
        self.assertNotEqual(a,comparison_key(packet))
        y['judgeComparisonKey']=comparison_key(packet)
        self.assertEqual(summarize({'reviews':[x,y]},{'machineReviewId':'b'})['sameProtocolRuns'],1)


if __name__=='__main__':unittest.main()
