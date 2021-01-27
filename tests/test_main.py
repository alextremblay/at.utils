from pathlib import Path
import time

from si_utils import main

import pytest
from _pytest.monkeypatch import MonkeyPatch


def clear_caches():
    "clear the caches of all cached functions in si_utils.main"
    for f in main.__dict__.values():
        if callable(f) and hasattr(f, 'cache'):
            f.cache = {}


def test_txt():
    res = main.txt("""
        one
        two
        three
        """)
    assert res == "one\ntwo\nthree\n"


def test_lst():
    res = main.lst("""
        one # superfluous comment
        two

        # empty space and line comment
        three
        """)
    assert res == ['one', 'two', 'three']


@pytest.fixture
def config_dirs(tmp_path: Path, monkeypatch: MonkeyPatch):
    "sets up get_config_file to search a specific set of tmp folders"
    site_conf = tmp_path.joinpath('site_config')
    site_conf.mkdir()
    user_conf = tmp_path.joinpath('user_config')
    user_conf.mkdir()
    monkeypatch.setenv("SI_UTILS_SITE_CONFIG", str(site_conf))
    monkeypatch.setenv("SI_UTILS_USER_CONFIG", str(user_conf))
    yield tmp_path
    clear_caches()


def test_get_config_file(config_dirs: Path, monkeypatch: MonkeyPatch):
    # Test the failure condition
    with pytest.raises(Exception):
        main.get_config_file_or_fail('some_nonexistant_app')
    assert main.get_config_file_or_none('some_nonexistant_app') is None

    # Test the success conditions
    config_dirs.joinpath('site_config/someapp.ini').write_text(' ')
    file = main.get_config_file_or_fail('someapp')
    assert file.exists()


def test_get_config_file_env_var(tmp_path: Path, monkeypatch: MonkeyPatch):
    # test the *_CONFIG_FILE env var
    test_file = tmp_path / 'test.ini'
    test_file.write_text(' ')
    monkeypatch.setenv('TEST_CONFIG_FILE', str(test_file))
    result = main.get_config_file_or_none('test')
    assert result.exists()


def test_get_config_obj(tmp_path: Path, monkeypatch: MonkeyPatch):
    # Test the failure condition
    test_file = tmp_path / 'badtest.yaml'
    test_file.write_text(' ')
    monkeypatch.setenv('BADTEST_CONFIG_FILE', str(test_file))
    with pytest.raises(Exception):
        main.get_config_obj_or_fail('badtest')

    # test ini
    test_file = tmp_path / 'test3.ini'
    test_file.write_text('[DEFAULT]\nkey1 = val1\nkey2 = val2')
    monkeypatch.setenv('TEST3_CONFIG_FILE', str(test_file))
    result = main.get_config_obj_or_fail('test3')
    assert result == {'key1': 'val1', 'key2': 'val2'}

    # test json
    test_file = tmp_path / 'test4.json'
    test_file.write_text('{"key1": "val1", "key2": "val2"}')
    monkeypatch.setenv('TEST4_CONFIG_FILE', str(test_file))
    result = main.get_config_obj_or_fail('test4')
    assert result == {'key1': 'val1', 'key2': 'val2'}


def test_get_config_key(tmp_path: Path, monkeypatch: MonkeyPatch):
    # test config file missing
    with pytest.raises(Exception):
        main.get_config_key_or_fail('test5', 'key1')

    # test key missing from config file
    test_file = tmp_path / 'test6.json'
    test_file.write_text('{"key2": "val2"}')
    monkeypatch.setenv('TEST6_CONFIG_FILE', str(test_file))
    with pytest.raises(Exception):
        main.get_config_key_or_fail('test6', 'key1')

    # test env var
    monkeypatch.setenv('TEST7_KEY1', 'env var value')
    result = main.get_config_key_or_fail('test7', 'key1')
    assert result == 'env var value'

    # test with config file
    test_file = tmp_path / 'test8.json'
    test_file.write_text('{"key1": "val1", "key2": "val2"}')
    monkeypatch.setenv('TEST8_CONFIG_FILE', str(test_file))
    result = main.get_config_key_or_fail('test8', 'key1')
    assert result == 'val1'


def test_get_cache_dir():
    # TODO: figure out how to safely mock root FS calls and properly test this function
    dir = main.get_cache_dir('test')
    assert dir.exists()


def test_timeit():
    # the clock starts as soon as the class is initialized
    timer = main.Timeit()
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
