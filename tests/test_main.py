from pathlib import Path
import time

from si_utils.main import lst, txt, get_config_file, \
    get_config_obj, get_config_key, Timeit

import pytest
from _pytest.monkeypatch import MonkeyPatch


def test_txt():
    res = txt("""
        one
        two
        three
        """)
    assert res == "one\ntwo\nthree\n"


def test_lst():
    res = lst("""
        one # superfluous comment
        two

        # empty space and line comment
        three
        """)
    assert res == ['one', 'two', 'three']


def test_get_config_file(tmp_path: Path, monkeypatch: MonkeyPatch):
    # Test the failure condition
    with pytest.raises(Exception):
        get_config_file('klsrjgbskvb')

    # test the *_CONFIG_FILE env var
    test_file = tmp_path / 'test.ini'
    test_file.write_text(' ')
    monkeypatch.setenv('TEST_CONFIG_FILE', str(test_file))
    result = get_config_file('test')
    assert result.exists()

    # get_config_file is cached. (or should be)
    assert len(get_config_file.cache) > 0

    # clear the cache
    get_config_file.cache = {}

    # test file lookup
    tmp_path.joinpath('test2.json').write_text(' ')
    monkeypatch.setenv('SI_UTILS_CONFIG_PATH', str(tmp_path))
    result = get_config_file('test2')
    assert result.name == 'test2.json'
    # clear the cache
    get_config_file.cache = {}

    # Need to find a way to mock /etc/xdg/si-utils and ~/.config/si-utils
    # to test config file lookup
    # tried pyfakefs, but it was too flaky


def test_get_config_obj(tmp_path: Path, monkeypatch: MonkeyPatch):
    # Test the failure condition
    with pytest.raises(Exception):
        test_file = tmp_path / 'badtest.yaml'
        test_file.write_text(' ')
        monkeypatch.setenv('BADTEST_CONFIG_FILE', str(test_file))
        get_config_obj('badtest')

    # test ini
    test_file = tmp_path / 'test3.ini'
    test_file.write_text('[DEFAULT]\nkey1 = val1\nkey2 = val2')
    monkeypatch.setenv('TEST3_CONFIG_FILE', str(test_file))
    result = get_config_obj('test3')
    assert result == {'key1': 'val1', 'key2': 'val2'}

    # test json
    test_file = tmp_path / 'test4.json'
    test_file.write_text('{"key1": "val1", "key2": "val2"}')
    monkeypatch.setenv('TEST4_CONFIG_FILE', str(test_file))
    result = get_config_obj('test4')
    assert result == {'key1': 'val1', 'key2': 'val2'}


def test_get_config_key(tmp_path: Path, monkeypatch: MonkeyPatch):
    # test env var
    monkeypatch.setenv('TEST5_KEY1', 'env var value')
    result = get_config_key('test5', 'key1')
    assert result == 'env var value'

    # test with config file
    test_file = tmp_path / 'test6.json'
    test_file.write_text('{"key1": "val1", "key2": "val2"}')
    monkeypatch.setenv('TEST6_CONFIG_FILE', str(test_file))
    result = get_config_key('test6', 'key1')
    assert result == 'val1'


def test_get_cache_dir():
    # TODO: figure out how to safely mock root FS calls and test this function
    pass


def test_timeit():
    # the clock starts as soon as the class is initialized
    timer = Timeit()
    time.sleep(0.1)
    timer.interval()  # record an interval
    assert 0.1 < timer.float < 0.101
    assert timer.str.startswith('0.1')
    time.sleep(0.5)
    timer.interval()

    # only the time elapsed since the start
    # of the last interval is recorded
    assert 0.5 < timer.float < 0.501
    assert timer.str.startswith('0.5')

    # timer.interval() is the same as timer.stop() except it starts a new
    # clock immediately after recording runtime for the previous clock
    timer.stop()
