"""Close/crash classification, including the systemd exit-reporting race."""
import os
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

with patch.object(os, 'getuid', return_value=1000, create=True), patch.dict(os.environ):
    module=runpy.run_path(str(Path(__file__).with_name('frame-jis-keyboard')),run_name='inspect_only')
classify=module['local_exit']


def status(state='inactive',pid=0,result='success',code=1,exit_status=0,substate='dead'):
    return SimpleNamespace(returncode=0,stdout='\n'.join((f'ActiveState={state}',f'MainPID={pid}',
        f'Result={result}',f'ExecMainCode={code}',f'ExecMainStatus={exit_status}',f'SubState={substate}')))


class Close(unittest.TestCase):
    def check(self,expected,*results,settle=0):
        with patch.dict(classify.__globals__,run=unittest.mock.Mock(side_effect=results)):
            self.assertEqual(classify(42,settle),expected)

    def test_normal_successful_close(self):self.check('closed',status())

    def test_retained_successful_exit_is_closed(self):
        self.check('closed',status('active',substate='exited'))

    def test_crash_or_error_remains_failure(self):
        for result in (status('failed',result='signal',code=2,exit_status=9),
                       status('failed',result='exit-code',exit_status=1),
                       status(code=2,exit_status=15)):
            self.check('failed',result)

    def test_running_success_fields_do_not_mean_close(self):
        self.check('unknown',status('active',42,code=0))

    def test_proc_exit_waits_for_systemd_final_status(self):
        self.check('closed',status('active',42,code=0),status(),settle=.2)

    def test_old_guard_does_not_own_a_new_process(self):
        self.check('replaced',status('active',43,code=0))


if __name__=='__main__':unittest.main()
