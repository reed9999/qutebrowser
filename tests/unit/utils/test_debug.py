# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for qutebrowser.utils.debug."""

import logging
import re
import time
import textwrap

import pytest
from PyQt5.QtCore import pyqtSignal, Qt, QEvent, QObject
from PyQt5.QtWidgets import QStyle, QFrame

from qutebrowser.utils import debug


@debug.log_events
class EventObject(QObject):

    pass


def test_log_events(qapp, caplog):
    obj = EventObject()
    qapp.postEvent(obj, QEvent(QEvent.User))
    qapp.processEvents()
    records = caplog.records()
    assert len(records) == 1
    assert records[0].msg == 'Event in test_debug.EventObject: User'


class SignalObject(QObject):

    signal1 = pyqtSignal()
    signal2 = pyqtSignal(str, str)

    def __repr__(self):
        """This is not a nice thing to do, but it makes our tests easier."""
        return '<repr>'


@debug.log_signals
class DecoratedSignalObject(SignalObject):

    pass


@pytest.fixture(params=[(SignalObject, True), (DecoratedSignalObject, False)])
def signal_obj(request):
    klass, wrap = request.param
    obj = klass()
    if wrap:
        debug.log_signals(obj)
    return obj


def test_log_signals(caplog, signal_obj):
    signal_obj.signal1.emit()
    signal_obj.signal2.emit('foo', 'bar')

    records = caplog.records()
    assert len(records) == 2
    assert records[0].msg == 'Signal in <repr>: signal1()'
    assert records[1].msg == "Signal in <repr>: signal2('foo', 'bar')"


class TestLogTime:

    def test_duration(self, caplog):
        logger_name = 'qt-tests'

        with caplog.atLevel(logging.DEBUG, logger_name):
            with debug.log_time(logger_name, action='foobar'):
                time.sleep(0.1)

            records = caplog.records()
            assert len(records) == 1

            pattern = re.compile(r'^Foobar took ([\d.]*) seconds\.$')
            match = pattern.match(records[0].msg)
            assert match

            duration = float(match.group(1))
            assert 0 < duration < 5

    def test_logger(self, caplog):
        """Test with an explicit logger instead of a name."""
        logger_name = 'qt-tests'

        with caplog.atLevel(logging.DEBUG, logger_name):
            with debug.log_time(logging.getLogger(logger_name)):
                pass

        assert len(caplog.records()) == 1


class TestQEnumKey:

    def test_metaobj(self):
        """Make sure the classes we use in the tests have a metaobj or not.

        If Qt/PyQt even changes and our tests wouldn't test the full
        functionality of qenum_key because of that, this test will tell us.
        """
        assert not hasattr(QStyle.PrimitiveElement, 'staticMetaObject')
        assert hasattr(QFrame, 'staticMetaObject')

    @pytest.mark.parametrize('base, value, klass, expected', [
        (QStyle, QStyle.PE_PanelButtonCommand, None, 'PE_PanelButtonCommand'),
        (QFrame, QFrame.Sunken, None, 'Sunken'),
        (QFrame, 0x0030, QFrame.Shadow, 'Sunken'),
        (QFrame, 0x1337, QFrame.Shadow, '0x1337'),
    ])
    def test_qenum_key(self, base, value, klass, expected):
        key = debug.qenum_key(base, value, klass=klass)
        assert key == expected

    def test_add_base(self):
        key = debug.qenum_key(QFrame, QFrame.Sunken, add_base=True)
        assert key == 'QFrame.Sunken'

    def test_int_noklass(self):
        """Test passing an int without explicit klass given."""
        with pytest.raises(TypeError):
            debug.qenum_key(QFrame, 42)


class TestQFlagsKey:

    """Tests for qutebrowser.utils.debug.qflags_key.

    https://github.com/The-Compiler/qutebrowser/issues/42
    """

    fixme = pytest.mark.xfail(reason="See issue #42", raises=AssertionError)

    @pytest.mark.parametrize('base, value, klass, expected', [
        fixme((Qt, Qt.AlignTop, None, 'AlignTop')),
        fixme((Qt, Qt.AlignLeft | Qt.AlignTop, None, 'AlignLeft|AlignTop')),
        (Qt, Qt.AlignCenter, None, 'AlignHCenter|AlignVCenter'),
        fixme((Qt, 0x0021, Qt.Alignment, 'AlignLeft|AlignTop')),
        (Qt, 0x1100, Qt.Alignment, '0x0100|0x1000'),
    ])
    def test_qflags_key(self, base, value, klass, expected):
        flags = debug.qflags_key(base, value, klass=klass)
        assert flags == expected

    @fixme
    def test_add_base(self):
        """Test with add_base=True."""
        flags = debug.qflags_key(Qt, Qt.AlignTop, add_base=True)
        assert flags == 'Qt.AlignTop'

    def test_int_noklass(self):
        """Test passing an int without explicit klass given."""
        with pytest.raises(TypeError):
            debug.qflags_key(Qt, 42)


@pytest.mark.parametrize('signal, expected', [
    (SignalObject().signal1, 'signal1'),
    (SignalObject().signal2, 'signal2'),
])
def test_signal_name(signal, expected):
    assert debug.signal_name(signal) == expected


@pytest.mark.parametrize('args, kwargs, expected', [
    ([], {}, ''),
    (None, None, ''),
    (['foo'], None, "'foo'"),
    (['foo', 'bar'], None, "'foo', 'bar'"),
    (None, {'foo': 'bar'}, "foo='bar'"),
    (['foo', 'bar'], {'baz': 'fish'}, "'foo', 'bar', baz='fish'"),
    (['x' * 300], None, "'{}".format('x' * 198 + '…')),
], ids=lambda val: str(val)[:20])
def test_format_args(args, kwargs, expected):
    assert debug.format_args(args, kwargs) == expected


def func():
    pass


@pytest.mark.parametrize('func, args, kwargs, full, expected', [
    (func, None, None, False, 'func()'),
    (func, [1, 2], None, False, 'func(1, 2)'),
    (func, [1, 2], None, True, 'test_debug.func(1, 2)'),
    (func, [1, 2], {'foo': 3}, False, 'func(1, 2, foo=3)'),
])
def test_format_call(func, args, kwargs, full, expected):
    assert debug.format_call(func, args, kwargs, full) == expected


@pytest.mark.parametrize('args, expected', [
    ([23, 42], 'fake(23, 42)'),
    (['x' * 201], "fake('{}\u2026)".format('x' * 198)),
    (['foo\nbar'], r"fake('foo\nbar')"),
], ids=lambda val: str(val)[:20])
def test_dbg_signal(stubs, args, expected):
    assert debug.dbg_signal(stubs.FakeSignal(), args) == expected


class TestGetAllObjects:

    class Object(QObject):

        def __init__(self, name, parent=None):
            self._name = name
            super().__init__(parent)

        def __repr__(self):
            return '<{}>'.format(self._name)


    def test_get_all_objects(self, stubs, monkeypatch):
        # pylint: disable=unused-variable
        widgets = [self.Object('Widget 1'), self.Object('Widget 2')]
        app = stubs.FakeQApplication(all_widgets=widgets)
        monkeypatch.setattr(debug, 'QApplication', app)

        root = QObject()
        o1 = self.Object('Object 1', root)
        o2 = self.Object('Object 2', o1)
        o3 = self.Object('Object 3', root)

        expected = textwrap.dedent("""
            Qt widgets - 2 objects:
                <Widget 1>
                <Widget 2>

            Qt objects - 3 objects:
                <Object 1>
                    <Object 2>
                <Object 3>

            global object registry - 0 objects:
        """).rstrip('\n')

        assert debug.get_all_objects(start_obj=root) == expected

    @pytest.mark.usefixtures('qapp')
    def test_get_all_objects_qapp(self):
        objects = debug.get_all_objects()
        event_dispatcher = '<PyQt5.QtCore.QAbstractEventDispatcher object at'
        session_manager = '<PyQt5.QtGui.QSessionManager object at'
        assert event_dispatcher in objects or session_manager in objects
