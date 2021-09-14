# pylint: disable=unused-argument
from pathlib import Path
import time

from at_utils import main, dev_utils

import pytest
from _pytest.monkeypatch import MonkeyPatch


def test_txt():
    res = main.txt(
        """
        one
        two
        three
        """
    )
    assert res == "one\ntwo\nthree\n"


def test_lst():
    res = main.lst(
        """
        one # superfluous comment
        two

        # empty space and line comment
        three
        """
    )
    assert res == ["one", "two", "three"]


def test_get_config_file(mock_paths: dev_utils.SIUtilsPaths):
    # Test the failure condition
    with pytest.raises(Exception) as exc_info:
        main.get_config_file_or_fail("some_nonexistant_app")
    assert "Could not find a valid config file" in exc_info.value.args[0]
    assert main.get_config_file_or_none("some_nonexistant_app") is None

    # Test the success conditions
    mock_paths.set_config_toml(" ")
    file = main.get_config_file_or_fail("test")
    assert file.exists()


# @pytest.mark.forked
def test_get_config_file_env_var(tmp_path: Path, monkeypatch: MonkeyPatch):
    # test the *_CONFIG_FILE env var
    test_file = tmp_path / "test.ini"
    test_file.write_text(" ")
    monkeypatch.setenv("TEST_CONFIG_FILE", str(test_file))
    result = main.get_config_file_or_none("test")
    assert result.exists()


# @pytest.mark.forked
def test_get_config_obj_raises(mock_paths: dev_utils.SIUtilsPaths):
    mock_paths.set_config_yaml(" ")
    with pytest.raises(Exception) as exc_info:
        main.get_config_obj_or_fail("test")
    error_message = "does not support config files of type .yaml."
    assert error_message in exc_info.value.args[0]


# @pytest.mark.forked
def test_get_config_obj_ini(mock_paths: dev_utils.SIUtilsPaths):
    mock_paths.set_config_ini(
        """
        [_common_]
        key1 = val1
        key2 = val2
        [extra]
        key = value
        """,
    )
    result = main.get_config_obj_or_fail("test")
    assert result == {"key1": "val1", "key2": "val2", "extra": {"key": "value"}}


# @pytest.mark.forked
def test_get_config_obj_json(mock_paths: dev_utils.SIUtilsPaths):
    mock_paths.set_config_json(
        """
        {
            "key1": "val1", 
            "key2": "val2"
        }
        """,
    )
    result = main.get_config_obj_or_fail("test")
    assert result == {"key1": "val1", "key2": "val2"}


# @pytest.mark.forked
def test_get_config_obj_toml(mock_paths: dev_utils.SIUtilsPaths):
    mock_paths.set_config_toml(
        """
        key1 = 'val1'
        key2 = 'val2'
        """,
    )
    result = main.get_config_obj_or_fail("test")
    assert result == {"key1": "val1", "key2": "val2"}


def test_get_config_key(tmp_path: Path, monkeypatch: MonkeyPatch):
    # test config file missing
    with pytest.raises(Exception):
        main.get_config_key_or_fail("test5", "key1")

    # test key missing from config file
    test_file = tmp_path / "test6.json"
    test_file.write_text('{"key2": "val2"}')
    monkeypatch.setenv("TEST6_CONFIG_FILE", str(test_file))
    with pytest.raises(Exception):
        main.get_config_key_or_fail("test6", "key1")

    # test env var
    monkeypatch.setenv("TEST7_KEY1", "env var value")
    result = main.get_config_key_or_fail("test7", "key1")
    assert result == "env var value"

    # test with config file
    test_file = tmp_path / "test8.json"
    test_file.write_text('{"key1": "val1", "key2": "val2"}')
    monkeypatch.setenv("TEST8_CONFIG_FILE", str(test_file))
    result = main.get_config_key_or_fail("test8", "key1")
    assert result == "val1"


def test_get_cache_dir(mock_paths: dev_utils.SIUtilsPaths):
    cache_dir = main.get_cache_dir("test")
    assert cache_dir.exists()

    cache_dir.joinpath("test.txt").touch()

    assert mock_paths.cache_dir.joinpath("test.txt").exists()


@pytest.mark.skip(
    """
This test relies on time.perf_counter and time.sleep, 
which don't always seem to play nicely together. 
This test is flaky, and exists as more of a living document / api contract than an actual test. 
Skipped by default, but should be run periodically to ensure Timeit API hasn't diverged from expectation"""
)
def test_timeit():
    # the clock starts as soon as the class is initialized
    timer = main.Timeit()
    time.sleep(0.1)
    timer.interval()  # record an interval
    assert 0.1 < timer.float < 0.101
    assert timer.str.startswith("0.1")
    time.sleep(0.5)
    timer.interval()

    # only the time elapsed since the start
    # of the last interval is recorded
    assert 0.5 < timer.float < 0.501
    assert timer.str.startswith("0.5")

    # timer.interval() is the same as timer.stop() except it starts a new
    # clock immediately after recording runtime for the previous clock
    timer.stop()
