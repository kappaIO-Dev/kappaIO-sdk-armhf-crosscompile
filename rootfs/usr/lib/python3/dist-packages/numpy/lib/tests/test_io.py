import numpy as np
import numpy.ma as ma
from numpy.ma.testutils import (TestCase, assert_equal, assert_array_equal,
    assert_raises, run_module_suite)
from numpy.testing import assert_warns, assert_, build_err_msg

import sys

import gzip
import os
import threading

from tempfile import mkstemp, NamedTemporaryFile
import time
from datetime import datetime
import warnings
import gc
from numpy.testing.utils import WarningManager

from numpy.lib._iotools import ConverterError, ConverterLockError, \
                               ConversionWarning
from numpy.compat import asbytes, asbytes_nested, bytes

if sys.version_info[0] >= 3:
    from io import BytesIO
    def StringIO(s=""):
        return BytesIO(asbytes(s))
else:
    from io import StringIO
    BytesIO = StringIO

MAJVER, MINVER = sys.version_info[:2]

def strptime(s, fmt=None):
    """This function is available in the datetime module only
    from Python >= 2.5.

    """
    if sys.version_info[0] >= 3:
        return datetime(*time.strptime(s.decode('latin1'), fmt)[:3])
    else:
        return datetime(*time.strptime(s, fmt)[:3])

class RoundtripTest(object):
    def roundtrip(self, save_func, *args, **kwargs):
        """
        save_func : callable
            Function used to save arrays to file.
        file_on_disk : bool
            If true, store the file on disk, instead of in a
            string buffer.
        save_kwds : dict
            Parameters passed to `save_func`.
        load_kwds : dict
            Parameters passed to `numpy.load`.
        args : tuple of arrays
            Arrays stored to file.

        """
        save_kwds = kwargs.get('save_kwds', {})
        load_kwds = kwargs.get('load_kwds', {})
        file_on_disk = kwargs.get('file_on_disk', False)

        if file_on_disk:
            # Do not delete the file on windows, because we can't
            # reopen an already opened file on that platform, so we
            # need to close the file and reopen it, implying no
            # automatic deletion.
            if sys.platform == 'win32' and MAJVER >= 2 and MINVER >= 6:
                target_file = NamedTemporaryFile(delete=False)
            else:
                target_file = NamedTemporaryFile()
            load_file = target_file.name
        else:
            target_file = StringIO()
            load_file = target_file

        arr = args

        save_func(target_file, *arr, **save_kwds)
        target_file.flush()
        target_file.seek(0)

        if sys.platform == 'win32' and not isinstance(target_file, BytesIO):
            target_file.close()

        arr_reloaded = np.load(load_file, **load_kwds)

        self.arr = arr
        self.arr_reloaded = arr_reloaded

    def test_array(self):
        a = np.array([[1, 2], [3, 4]], float)
        self.roundtrip(a)

        a = np.array([[1, 2], [3, 4]], int)
        self.roundtrip(a)

        a = np.array([[1 + 5j, 2 + 6j], [3 + 7j, 4 + 8j]], dtype=np.csingle)
        self.roundtrip(a)

        a = np.array([[1 + 5j, 2 + 6j], [3 + 7j, 4 + 8j]], dtype=np.cdouble)
        self.roundtrip(a)

    def test_1D(self):
        a = np.array([1, 2, 3, 4], int)
        self.roundtrip(a)

    @np.testing.dec.knownfailureif(sys.platform == 'win32', "Fail on Win32")
    def test_mmap(self):
        a = np.array([[1, 2.5], [4, 7.3]])
        self.roundtrip(a, file_on_disk=True, load_kwds={'mmap_mode': 'r'})

    def test_record(self):
        a = np.array([(1, 2), (3, 4)], dtype=[('x', 'i4'), ('y', 'i4')])
        self.roundtrip(a)

class TestSaveLoad(RoundtripTest, TestCase):
    def roundtrip(self, *args, **kwargs):
        RoundtripTest.roundtrip(self, np.save, *args, **kwargs)
        assert_equal(self.arr[0], self.arr_reloaded)

class TestSavezLoad(RoundtripTest, TestCase):
    def roundtrip(self, *args, **kwargs):
        RoundtripTest.roundtrip(self, np.savez, *args, **kwargs)
        for n, arr in enumerate(self.arr):
            assert_equal(arr, self.arr_reloaded['arr_%d' % n])

    def test_multiple_arrays(self):
        a = np.array([[1, 2], [3, 4]], float)
        b = np.array([[1 + 2j, 2 + 7j], [3 - 6j, 4 + 12j]], complex)
        self.roundtrip(a, b)

    def test_named_arrays(self):
        a = np.array([[1, 2], [3, 4]], float)
        b = np.array([[1 + 2j, 2 + 7j], [3 - 6j, 4 + 12j]], complex)
        c = StringIO()
        np.savez(c, file_a=a, file_b=b)
        c.seek(0)
        l = np.load(c)
        assert_equal(a, l['file_a'])
        assert_equal(b, l['file_b'])

    def test_savez_filename_clashes(self):
        # Test that issue #852 is fixed
        # and savez functions in multithreaded environment

        def writer(error_list):
            fd, tmp = mkstemp(suffix='.npz')
            os.close(fd)
            try:
                arr = np.random.randn(500, 500)
                try:
                    np.savez(tmp, arr=arr)
                except OSError as err:
                    error_list.append(err)
            finally:
                os.remove(tmp)

        errors = []
        threads = [threading.Thread(target=writer, args=(errors,))
                   for j in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            raise AssertionError(errors)

class TestSaveTxt(TestCase):
    def test_array(self):
        a = np.array([[1, 2], [3, 4]], float)
        fmt = "%.18e"
        c = StringIO()
        np.savetxt(c, a, fmt=fmt)
        c.seek(0)
        assert_equal(c.readlines(),
                     asbytes_nested(
            [(fmt + ' ' + fmt + '\n') % (1, 2),
             (fmt + ' ' + fmt + '\n') % (3, 4)]))

        a = np.array([[1, 2], [3, 4]], int)
        c = StringIO()
        np.savetxt(c, a, fmt='%d')
        c.seek(0)
        assert_equal(c.readlines(), asbytes_nested(['1 2\n', '3 4\n']))

    def test_1D(self):
        a = np.array([1, 2, 3, 4], int)
        c = StringIO()
        np.savetxt(c, a, fmt='%d')
        c.seek(0)
        lines = c.readlines()
        assert_equal(lines, asbytes_nested(['1\n', '2\n', '3\n', '4\n']))

    def test_record(self):
        a = np.array([(1, 2), (3, 4)], dtype=[('x', 'i4'), ('y', 'i4')])
        c = StringIO()
        np.savetxt(c, a, fmt='%d')
        c.seek(0)
        assert_equal(c.readlines(), asbytes_nested(['1 2\n', '3 4\n']))

    def test_delimiter(self):
        a = np.array([[1., 2.], [3., 4.]])
        c = StringIO()
        np.savetxt(c, a, delimiter=asbytes(','), fmt='%d')
        c.seek(0)
        assert_equal(c.readlines(), asbytes_nested(['1,2\n', '3,4\n']))

    def test_format(self):
        a = np.array([(1, 2), (3, 4)])
        c = StringIO()
        # Sequence of formats
        np.savetxt(c, a, fmt=['%02d', '%3.1f'])
        c.seek(0)
        assert_equal(c.readlines(), asbytes_nested(['01 2.0\n', '03 4.0\n']))

        # A single multiformat string
        c = StringIO()
        np.savetxt(c, a, fmt='%02d : %3.1f')
        c.seek(0)
        lines = c.readlines()
        assert_equal(lines, asbytes_nested(['01 : 2.0\n', '03 : 4.0\n']))

        # Specify delimiter, should be overiden
        c = StringIO()
        np.savetxt(c, a, fmt='%02d : %3.1f', delimiter=',')
        c.seek(0)
        lines = c.readlines()
        assert_equal(lines, asbytes_nested(['01 : 2.0\n', '03 : 4.0\n']))

    def test_file_roundtrip(self):
        f, name = mkstemp()
        os.close(f)
        try:
            a = np.array([(1, 2), (3, 4)])
            np.savetxt(name, a)
            b = np.loadtxt(name)
            assert_array_equal(a, b)
        finally:
            os.unlink(name)

    def test_complex_arrays(self):
        ncols = 2
        nrows = 2
        a = np.zeros((ncols, nrows), dtype=np.complex128)
        re = np.pi
        im = np.e
        a[:] = re + 1.0j * im
        # One format only
        c = StringIO()
        np.savetxt(c, a, fmt=' %+.3e')
        c.seek(0)
        lines = c.readlines()
        _assert_floatstr_lines_equal(lines, asbytes_nested([
            ' ( +3.142e+00+ +2.718e+00j)  ( +3.142e+00+ +2.718e+00j)\n',
            ' ( +3.142e+00+ +2.718e+00j)  ( +3.142e+00+ +2.718e+00j)\n']))
        # One format for each real and imaginary part
        c = StringIO()
        np.savetxt(c, a, fmt='  %+.3e' * 2 * ncols)
        c.seek(0)
        lines = c.readlines()
        _assert_floatstr_lines_equal(lines, asbytes_nested([
            '  +3.142e+00  +2.718e+00  +3.142e+00  +2.718e+00\n',
            '  +3.142e+00  +2.718e+00  +3.142e+00  +2.718e+00\n']))
        # One format for each complex number
        c = StringIO()
        np.savetxt(c, a, fmt=['(%.3e%+.3ej)'] * ncols)
        c.seek(0)
        lines = c.readlines()
        _assert_floatstr_lines_equal(lines, asbytes_nested([
            '(3.142e+00+2.718e+00j) (3.142e+00+2.718e+00j)\n',
            '(3.142e+00+2.718e+00j) (3.142e+00+2.718e+00j)\n']))


def _assert_floatstr_lines_equal(actual_lines, expected_lines):
    """A string comparison function that also works on Windows + Python 2.5.

    This is necessary because Python 2.5 on Windows inserts an extra 0 in
    the exponent of the string representation of floating point numbers.

    Only used in TestSaveTxt.test_complex_arrays, no attempt made to make this
    more generic.

    Once Python 2.5 compatibility is dropped, simply use `assert_equal` instead
    of this function.
    """
    for actual, expected in zip(actual_lines, expected_lines):
        if actual != expected:
            expected_win25 = expected.replace("e+00", "e+000")
            if actual != expected_win25:
                msg = build_err_msg([actual, expected], '', verbose=True)
                raise AssertionError(msg)


class TestLoadTxt(TestCase):
    def test_record(self):
        c = StringIO()
        c.write(asbytes('1 2\n3 4'))
        c.seek(0)
        x = np.loadtxt(c, dtype=[('x', np.int32), ('y', np.int32)])
        a = np.array([(1, 2), (3, 4)], dtype=[('x', 'i4'), ('y', 'i4')])
        assert_array_equal(x, a)

        d = StringIO()
        d.write(asbytes('M 64.0 75.0\nF 25.0 60.0'))
        d.seek(0)
        mydescriptor = {'names': ('gender', 'age', 'weight'),
                        'formats': ('S1',
                                    'i4', 'f4')}
        b = np.array([('M', 64.0, 75.0),
                      ('F', 25.0, 60.0)], dtype=mydescriptor)
        y = np.loadtxt(d, dtype=mydescriptor)
        assert_array_equal(y, b)

    def test_array(self):
        c = StringIO()
        c.write(asbytes('1 2\n3 4'))

        c.seek(0)
        x = np.loadtxt(c, dtype=int)
        a = np.array([[1, 2], [3, 4]], int)
        assert_array_equal(x, a)

        c.seek(0)
        x = np.loadtxt(c, dtype=float)
        a = np.array([[1, 2], [3, 4]], float)
        assert_array_equal(x, a)

    def test_1D(self):
        c = StringIO()
        c.write(asbytes('1\n2\n3\n4\n'))
        c.seek(0)
        x = np.loadtxt(c, dtype=int)
        a = np.array([1, 2, 3, 4], int)
        assert_array_equal(x, a)

        c = StringIO()
        c.write(asbytes('1,2,3,4\n'))
        c.seek(0)
        x = np.loadtxt(c, dtype=int, delimiter=',')
        a = np.array([1, 2, 3, 4], int)
        assert_array_equal(x, a)

    def test_missing(self):
        c = StringIO()
        c.write(asbytes('1,2,3,,5\n'))
        c.seek(0)
        x = np.loadtxt(c, dtype=int, delimiter=',', \
            converters={3:lambda s: int(s or - 999)})
        a = np.array([1, 2, 3, -999, 5], int)
        assert_array_equal(x, a)

    def test_converters_with_usecols(self):
        c = StringIO()
        c.write(asbytes('1,2,3,,5\n6,7,8,9,10\n'))
        c.seek(0)
        x = np.loadtxt(c, dtype=int, delimiter=',', \
            converters={3:lambda s: int(s or - 999)}, \
            usecols=(1, 3,))
        a = np.array([[2, -999], [7, 9]], int)
        assert_array_equal(x, a)

    def test_comments(self):
        c = StringIO()
        c.write(asbytes('# comment\n1,2,3,5\n'))
        c.seek(0)
        x = np.loadtxt(c, dtype=int, delimiter=',', \
            comments='#')
        a = np.array([1, 2, 3, 5], int)
        assert_array_equal(x, a)

    def test_skiprows(self):
        c = StringIO()
        c.write(asbytes('comment\n1,2,3,5\n'))
        c.seek(0)
        x = np.loadtxt(c, dtype=int, delimiter=',', \
            skiprows=1)
        a = np.array([1, 2, 3, 5], int)
        assert_array_equal(x, a)

        c = StringIO()
        c.write(asbytes('# comment\n1,2,3,5\n'))
        c.seek(0)
        x = np.loadtxt(c, dtype=int, delimiter=',', \
            skiprows=1)
        a = np.array([1, 2, 3, 5], int)
        assert_array_equal(x, a)

    def test_usecols(self):
        a = np.array([[1, 2], [3, 4]], float)
        c = StringIO()
        np.savetxt(c, a)
        c.seek(0)
        x = np.loadtxt(c, dtype=float, usecols=(1,))
        assert_array_equal(x, a[:, 1])

        a = np.array([[1, 2, 3], [3, 4, 5]], float)
        c = StringIO()
        np.savetxt(c, a)
        c.seek(0)
        x = np.loadtxt(c, dtype=float, usecols=(1, 2))
        assert_array_equal(x, a[:, 1:])

        # Testing with arrays instead of tuples.
        c.seek(0)
        x = np.loadtxt(c, dtype=float, usecols=np.array([1, 2]))
        assert_array_equal(x, a[:, 1:])

        # Checking with dtypes defined converters.
        data = '''JOE 70.1 25.3
                BOB 60.5 27.9
                '''
        c = StringIO(data)
        names = ['stid', 'temp']
        dtypes = ['S4', 'f8']
        arr = np.loadtxt(c, usecols=(0, 2), dtype=list(zip(names, dtypes)))
        assert_equal(arr['stid'], asbytes_nested(["JOE", "BOB"]))
        assert_equal(arr['temp'], [25.3, 27.9])

    def test_fancy_dtype(self):
        c = StringIO()
        c.write(asbytes('1,2,3.0\n4,5,6.0\n'))
        c.seek(0)
        dt = np.dtype([('x', int), ('y', [('t', int), ('s', float)])])
        x = np.loadtxt(c, dtype=dt, delimiter=',')
        a = np.array([(1, (2, 3.0)), (4, (5, 6.0))], dt)
        assert_array_equal(x, a)

    def test_shaped_dtype(self):
        c = StringIO("aaaa  1.0  8.0  1 2 3 4 5 6")
        dt = np.dtype([('name', 'S4'), ('x', float), ('y', float),
                       ('block', int, (2, 3))])
        x = np.loadtxt(c, dtype=dt)
        a = np.array([('aaaa', 1.0, 8.0, [[1, 2, 3], [4, 5, 6]])],
                     dtype=dt)
        assert_array_equal(x, a)

    def test_3d_shaped_dtype(self):
        c = StringIO("aaaa  1.0  8.0  1 2 3 4 5 6 7 8 9 10 11 12")
        dt = np.dtype([('name', 'S4'), ('x', float), ('y', float),
                       ('block', int, (2, 2, 3))])
        x = np.loadtxt(c, dtype=dt)
        a = np.array([('aaaa', 1.0, 8.0, [[[1, 2, 3], [4, 5, 6]],[[7, 8, 9], [10, 11, 12]]])],
                     dtype=dt)
        assert_array_equal(x, a)

    def test_empty_file(self):
        warnings.filterwarnings("ignore", message="loadtxt: Empty input file:")
        c = StringIO()
        x = np.loadtxt(c)
        assert_equal(x.shape, (0,))
        x = np.loadtxt(c, dtype=np.int64)
        assert_equal(x.shape, (0,))
        assert_(x.dtype == np.int64)


    def test_unused_converter(self):
        c = StringIO()
        c.writelines([asbytes('1 21\n'), asbytes('3 42\n')])
        c.seek(0)
        data = np.loadtxt(c, usecols=(1,),
                          converters={0: lambda s: int(s, 16)})
        assert_array_equal(data, [21, 42])

        c.seek(0)
        data = np.loadtxt(c, usecols=(1,),
                          converters={1: lambda s: int(s, 16)})
        assert_array_equal(data, [33, 66])

    def test_dtype_with_object(self):
        "Test using an explicit dtype with an object"
        from datetime import date
        import time
        data = asbytes(""" 1; 2001-01-01
                           2; 2002-01-31 """)
        ndtype = [('idx', int), ('code', np.object)]
        func = lambda s: strptime(s.strip(), "%Y-%m-%d")
        converters = {1: func}
        test = np.loadtxt(StringIO(data), delimiter=";", dtype=ndtype,
                             converters=converters)
        control = np.array([(1, datetime(2001, 1, 1)), (2, datetime(2002, 1, 31))],
                           dtype=ndtype)
        assert_equal(test, control)

    def test_uint64_type(self):
        tgt = (9223372043271415339, 9223372043271415853)
        c = StringIO()
        c.write(asbytes("%s %s" % tgt))
        c.seek(0)
        res = np.loadtxt(c, dtype=np.uint64)
        assert_equal(res, tgt)

    def test_int64_type(self):
        tgt = (-9223372036854775807, 9223372036854775807)
        c = StringIO()
        c.write(asbytes("%s %s" % tgt))
        c.seek(0)
        res = np.loadtxt(c, dtype=np.int64)
        assert_equal(res, tgt)

    def test_universal_newline(self):
        f, name = mkstemp()
        os.write(f, asbytes('1 21\r3 42\r'))
        os.close(f)

        try:
            data = np.loadtxt(name)
            assert_array_equal(data, [[1, 21], [3, 42]])
        finally:
            os.unlink(name)

    def test_empty_field_after_tab(self):
        c = StringIO()
        c.write(asbytes('1 \t2 \t3\tstart \n4\t5\t6\t  \n7\t8\t9.5\t'))
        c.seek(0)
        dt = { 'names': ('x', 'y', 'z', 'comment'),
               'formats': ('<i4', '<i4', '<f4', '|S8')}
        x = np.loadtxt(c, dtype=dt, delimiter='\t')
        a = np.array([asbytes('start '), asbytes('  '), asbytes('')])
        assert_array_equal(x['comment'], a)

    def test_structure_unpack(self):
        txt = StringIO(asbytes("M 21 72\nF 35 58"))
        dt = { 'names': ('a', 'b', 'c'), 'formats': ('|S1', '<i4', '<f4')}
        a, b, c = np.loadtxt(txt, dtype=dt, unpack=True)
        assert_(a.dtype.str == '|S1')
        assert_(b.dtype.str == '<i4')
        assert_(c.dtype.str == '<f4')
        assert_array_equal(a, np.array([asbytes('M'), asbytes('F')]))
        assert_array_equal(b, np.array([21, 35]))
        assert_array_equal(c, np.array([ 72.,  58.]))

    def test_ndmin_keyword(self):
        c = StringIO()
        c.write(asbytes('1,2,3\n4,5,6'))
        c.seek(0)
        assert_raises(ValueError, np.loadtxt, c, ndmin=3)
        c.seek(0)
        assert_raises(ValueError, np.loadtxt, c, ndmin=1.5)
        c.seek(0)
        x = np.loadtxt(c, dtype=int, delimiter=',', ndmin=1)
        a = np.array([[1, 2, 3], [4, 5, 6]])
        assert_array_equal(x, a)
        d = StringIO()
        d.write(asbytes('0,1,2'))
        d.seek(0)
        x = np.loadtxt(d, dtype=int, delimiter=',', ndmin=2)
        assert_(x.shape == (1, 3))
        d.seek(0)
        x = np.loadtxt(d, dtype=int, delimiter=',', ndmin=1)
        assert_(x.shape == (3,))
        d.seek(0)
        x = np.loadtxt(d, dtype=int, delimiter=',', ndmin=0)
        assert_(x.shape == (3,))
        e = StringIO()
        e.write(asbytes('0\n1\n2'))
        e.seek(0)
        x = np.loadtxt(e, dtype=int, delimiter=',', ndmin=2)
        assert_(x.shape == (3, 1))
        e.seek(0)
        x = np.loadtxt(e, dtype=int, delimiter=',', ndmin=1)
        assert_(x.shape == (3,))
        e.seek(0)
        x = np.loadtxt(e, dtype=int, delimiter=',', ndmin=0)
        assert_(x.shape == (3,))
        f = StringIO()
        assert_(np.loadtxt(f, ndmin=2).shape == (0, 1,))
        assert_(np.loadtxt(f, ndmin=1).shape == (0,))

    def test_generator_source(self):
        def count():
            for i in range(10):
                yield asbytes("%d" % i)

        res = np.loadtxt(count())
        assert_array_equal(res, np.arange(10))

class Testfromregex(TestCase):
    def test_record(self):
        c = StringIO()
        c.write(asbytes('1.312 foo\n1.534 bar\n4.444 qux'))
        c.seek(0)

        dt = [('num', np.float64), ('val', 'S3')]
        x = np.fromregex(c, r"([0-9.]+)\s+(...)", dt)
        a = np.array([(1.312, 'foo'), (1.534, 'bar'), (4.444, 'qux')],
                     dtype=dt)
        assert_array_equal(x, a)

    def test_record_2(self):
        c = StringIO()
        c.write(asbytes('1312 foo\n1534 bar\n4444 qux'))
        c.seek(0)

        dt = [('num', np.int32), ('val', 'S3')]
        x = np.fromregex(c, r"(\d+)\s+(...)", dt)
        a = np.array([(1312, 'foo'), (1534, 'bar'), (4444, 'qux')],
                     dtype=dt)
        assert_array_equal(x, a)

    def test_record_3(self):
        c = StringIO()
        c.write(asbytes('1312 foo\n1534 bar\n4444 qux'))
        c.seek(0)

        dt = [('num', np.float64)]
        x = np.fromregex(c, r"(\d+)\s+...", dt)
        a = np.array([(1312,), (1534,), (4444,)], dtype=dt)
        assert_array_equal(x, a)


#####--------------------------------------------------------------------------


class TestFromTxt(TestCase):
    #
    def test_record(self):
        "Test w/ explicit dtype"
        data = StringIO(asbytes('1 2\n3 4'))
#        data.seek(0)
        test = np.ndfromtxt(data, dtype=[('x', np.int32), ('y', np.int32)])
        control = np.array([(1, 2), (3, 4)], dtype=[('x', 'i4'), ('y', 'i4')])
        assert_equal(test, control)
        #
        data = StringIO('M 64.0 75.0\nF 25.0 60.0')
#        data.seek(0)
        descriptor = {'names': ('gender', 'age', 'weight'),
                      'formats': ('S1', 'i4', 'f4')}
        control = np.array([('M', 64.0, 75.0), ('F', 25.0, 60.0)],
                           dtype=descriptor)
        test = np.ndfromtxt(data, dtype=descriptor)
        assert_equal(test, control)

    def test_array(self):
        "Test outputing a standard ndarray"
        data = StringIO('1 2\n3 4')
        control = np.array([[1, 2], [3, 4]], dtype=int)
        test = np.ndfromtxt(data, dtype=int)
        assert_array_equal(test, control)
        #
        data.seek(0)
        control = np.array([[1, 2], [3, 4]], dtype=float)
        test = np.loadtxt(data, dtype=float)
        assert_array_equal(test, control)

    def test_1D(self):
        "Test squeezing to 1D"
        control = np.array([1, 2, 3, 4], int)
        #
        data = StringIO('1\n2\n3\n4\n')
        test = np.ndfromtxt(data, dtype=int)
        assert_array_equal(test, control)
        #
        data = StringIO('1,2,3,4\n')
        test = np.ndfromtxt(data, dtype=int, delimiter=asbytes(','))
        assert_array_equal(test, control)

    def test_comments(self):
        "Test the stripping of comments"
        control = np.array([1, 2, 3, 5], int)
        # Comment on its own line
        data = StringIO('# comment\n1,2,3,5\n')
        test = np.ndfromtxt(data, dtype=int, delimiter=asbytes(','), comments=asbytes('#'))
        assert_equal(test, control)
        # Comment at the end of a line
        data = StringIO('1,2,3,5# comment\n')
        test = np.ndfromtxt(data, dtype=int, delimiter=asbytes(','), comments=asbytes('#'))
        assert_equal(test, control)

    def test_skiprows(self):
        "Test row skipping"
        control = np.array([1, 2, 3, 5], int)
        kwargs = dict(dtype=int, delimiter=asbytes(','))
        #
        data = StringIO('comment\n1,2,3,5\n')
        test = np.ndfromtxt(data, skip_header=1, **kwargs)
        assert_equal(test, control)
        #
        data = StringIO('# comment\n1,2,3,5\n')
        test = np.loadtxt(data, skiprows=1, **kwargs)
        assert_equal(test, control)

    def test_skip_footer(self):
        data = ["# %i" % i for i in range(1, 6)]
        data.append("A, B, C")
        data.extend(["%i,%3.1f,%03s" % (i, i, i) for i in range(51)])
        data[-1] = "99,99"
        kwargs = dict(delimiter=",", names=True, skip_header=5, skip_footer=10)
        test = np.genfromtxt(StringIO(asbytes("\n".join(data))), **kwargs)
        ctrl = np.array([("%f" % i, "%f" % i, "%f" % i) for i in range(41)],
                        dtype=[(_, float) for _ in "ABC"])
        assert_equal(test, ctrl)

    def test_skip_footer_with_invalid(self):
        import warnings
        basestr = '1 1\n2 2\n3 3\n4 4\n5  \n6  \n7  \n'
        warnings.filterwarnings("ignore")
        # Footer too small to get rid of all invalid values
        assert_raises(ValueError, np.genfromtxt,
                      StringIO(basestr), skip_footer=1)
#        except ValueError:
#            pass
        a = np.genfromtxt(StringIO(basestr), skip_footer=1, invalid_raise=False)
        assert_equal(a, np.array([[1., 1.], [2., 2.], [3., 3.], [4., 4.]]))
        #
        a = np.genfromtxt(StringIO(basestr), skip_footer=3)
        assert_equal(a, np.array([[1., 1.], [2., 2.], [3., 3.], [4., 4.]]))
        #
        basestr = '1 1\n2  \n3 3\n4 4\n5  \n6 6\n7 7\n'
        a = np.genfromtxt(StringIO(basestr), skip_footer=1, invalid_raise=False)
        assert_equal(a, np.array([[1., 1.], [3., 3.], [4., 4.], [6., 6.]]))
        a = np.genfromtxt(StringIO(basestr), skip_footer=3, invalid_raise=False)
        assert_equal(a, np.array([[1., 1.], [3., 3.], [4., 4.]]))
        warnings.resetwarnings()


    def test_header(self):
        "Test retrieving a header"
        data = StringIO('gender age weight\nM 64.0 75.0\nF 25.0 60.0')
        test = np.ndfromtxt(data, dtype=None, names=True)
        control = {'gender': np.array(asbytes_nested(['M', 'F'])),
                   'age': np.array([64.0, 25.0]),
                   'weight': np.array([75.0, 60.0])}
        assert_equal(test['gender'], control['gender'])
        assert_equal(test['age'], control['age'])
        assert_equal(test['weight'], control['weight'])

    def test_auto_dtype(self):
        "Test the automatic definition of the output dtype"
        data = StringIO('A 64 75.0 3+4j True\nBCD 25 60.0 5+6j False')
        test = np.ndfromtxt(data, dtype=None)
        control = [np.array(asbytes_nested(['A', 'BCD'])),
                   np.array([64, 25]),
                   np.array([75.0, 60.0]),
                   np.array([3 + 4j, 5 + 6j]),
                   np.array([True, False]), ]
        assert_equal(test.dtype.names, ['f0', 'f1', 'f2', 'f3', 'f4'])
        for (i, ctrl) in enumerate(control):
            assert_equal(test['f%i' % i], ctrl)


    def test_auto_dtype_uniform(self):
        "Tests whether the output dtype can be uniformized"
        data = StringIO('1 2 3 4\n5 6 7 8\n')
        test = np.ndfromtxt(data, dtype=None)
        control = np.array([[1, 2, 3, 4], [5, 6, 7, 8]])
        assert_equal(test, control)


    def test_fancy_dtype(self):
        "Check that a nested dtype isn't MIA"
        data = StringIO('1,2,3.0\n4,5,6.0\n')
        fancydtype = np.dtype([('x', int), ('y', [('t', int), ('s', float)])])
        test = np.ndfromtxt(data, dtype=fancydtype, delimiter=',')
        control = np.array([(1, (2, 3.0)), (4, (5, 6.0))], dtype=fancydtype)
        assert_equal(test, control)


    def test_names_overwrite(self):
        "Test overwriting the names of the dtype"
        descriptor = {'names': ('g', 'a', 'w'),
                      'formats': ('S1', 'i4', 'f4')}
        data = StringIO('M 64.0 75.0\nF 25.0 60.0')
        names = ('gender', 'age', 'weight')
        test = np.ndfromtxt(data, dtype=descriptor, names=names)
        descriptor['names'] = names
        control = np.array([('M', 64.0, 75.0),
                            ('F', 25.0, 60.0)], dtype=descriptor)
        assert_equal(test, control)


    def test_commented_header(self):
        "Check that names can be retrieved even if the line is commented out."
        data = StringIO("""
#gender age weight
M   21  72.100000
F   35  58.330000
M   33  21.99
        """)
        # The # is part of the first name and should be deleted automatically.
        test = np.genfromtxt(data, names=True, dtype=None)
        ctrl = np.array([('M', 21, 72.1), ('F', 35, 58.33), ('M', 33, 21.99)],
                  dtype=[('gender', '|S1'), ('age', int), ('weight', float)])
        assert_equal(test, ctrl)
        # Ditto, but we should get rid of the first element
        data = StringIO("""
# gender age weight
M   21  72.100000
F   35  58.330000
M   33  21.99
        """)
        test = np.genfromtxt(data, names=True, dtype=None)
        assert_equal(test, ctrl)


    def test_autonames_and_usecols(self):
        "Tests names and usecols"
        data = StringIO('A B C D\n aaaa 121 45 9.1')
        test = np.ndfromtxt(data, usecols=('A', 'C', 'D'),
                            names=True, dtype=None)
        control = np.array(('aaaa', 45, 9.1),
                           dtype=[('A', '|S4'), ('C', int), ('D', float)])
        assert_equal(test, control)


    def test_converters_with_usecols(self):
        "Test the combination user-defined converters and usecol"
        data = StringIO('1,2,3,,5\n6,7,8,9,10\n')
        test = np.ndfromtxt(data, dtype=int, delimiter=',',
                            converters={3:lambda s: int(s or - 999)},
                            usecols=(1, 3,))
        control = np.array([[2, -999], [7, 9]], int)
        assert_equal(test, control)

    def test_converters_with_usecols_and_names(self):
        "Tests names and usecols"
        data = StringIO('A B C D\n aaaa 121 45 9.1')
        test = np.ndfromtxt(data, usecols=('A', 'C', 'D'), names=True,
                            dtype=None, converters={'C':lambda s: 2 * int(s)})
        control = np.array(('aaaa', 90, 9.1),
            dtype=[('A', '|S4'), ('C', int), ('D', float)])
        assert_equal(test, control)

    def test_converters_cornercases(self):
        "Test the conversion to datetime."
        converter = {'date': lambda s: strptime(s, '%Y-%m-%d %H:%M:%SZ')}
        data = StringIO('2009-02-03 12:00:00Z, 72214.0')
        test = np.ndfromtxt(data, delimiter=',', dtype=None,
                            names=['date', 'stid'], converters=converter)
        control = np.array((datetime(2009, 0o2, 0o3), 72214.),
                           dtype=[('date', np.object_), ('stid', float)])
        assert_equal(test, control)


    def test_unused_converter(self):
        "Test whether unused converters are forgotten"
        data = StringIO("1 21\n  3 42\n")
        test = np.ndfromtxt(data, usecols=(1,),
                            converters={0: lambda s: int(s, 16)})
        assert_equal(test, [21, 42])
        #
        data.seek(0)
        test = np.ndfromtxt(data, usecols=(1,),
                            converters={1: lambda s: int(s, 16)})
        assert_equal(test, [33, 66])


    def test_invalid_converter(self):
        strip_rand = lambda x : float((asbytes('r') in x.lower() and x.split()[-1]) or
                                      (not asbytes('r') in x.lower() and x.strip() or 0.0))
        strip_per = lambda x : float((asbytes('%') in x.lower() and x.split()[0]) or
                                     (not asbytes('%') in x.lower() and x.strip() or 0.0))
        s = StringIO("D01N01,10/1/2003 ,1 %,R 75,400,600\r\n" \
                              "L24U05,12/5/2003, 2 %,1,300, 150.5\r\n"
                              "D02N03,10/10/2004,R 1,,7,145.55")
        kwargs = dict(converters={2 : strip_per, 3 : strip_rand}, delimiter=",",
                      dtype=None)
        assert_raises(ConverterError, np.genfromtxt, s, **kwargs)

    def test_tricky_converter_bug1666(self):
        "Test some corner case"
        s = StringIO('q1,2\nq3,4')
        cnv = lambda s:float(s[1:])
        test = np.genfromtxt(s, delimiter=',', converters={0:cnv})
        control = np.array([[1., 2.], [3., 4.]])
        assert_equal(test, control)



    def test_dtype_with_converters(self):
        dstr = "2009; 23; 46"
        test = np.ndfromtxt(StringIO(dstr,),
                            delimiter=";", dtype=float, converters={0:bytes})
        control = np.array([('2009', 23., 46)],
                           dtype=[('f0', '|S4'), ('f1', float), ('f2', float)])
        assert_equal(test, control)
        test = np.ndfromtxt(StringIO(dstr,),
                            delimiter=";", dtype=float, converters={0:float})
        control = np.array([2009., 23., 46],)
        assert_equal(test, control)


    def test_dtype_with_object(self):
        "Test using an explicit dtype with an object"
        from datetime import date
        import time
        data = asbytes(""" 1; 2001-01-01
                           2; 2002-01-31 """)
        ndtype = [('idx', int), ('code', np.object)]
        func = lambda s: strptime(s.strip(), "%Y-%m-%d")
        converters = {1: func}
        test = np.genfromtxt(StringIO(data), delimiter=";", dtype=ndtype,
                             converters=converters)
        control = np.array([(1, datetime(2001, 1, 1)), (2, datetime(2002, 1, 31))],
                           dtype=ndtype)
        assert_equal(test, control)
        #
        ndtype = [('nest', [('idx', int), ('code', np.object)])]
        try:
            test = np.genfromtxt(StringIO(data), delimiter=";",
                                 dtype=ndtype, converters=converters)
        except NotImplementedError:
            pass
        else:
            errmsg = "Nested dtype involving objects should be supported."
            raise AssertionError(errmsg)


    def test_userconverters_with_explicit_dtype(self):
        "Test user_converters w/ explicit (standard) dtype"
        data = StringIO('skip,skip,2001-01-01,1.0,skip')
        test = np.genfromtxt(data, delimiter=",", names=None, dtype=float,
                             usecols=(2, 3), converters={2: bytes})
        control = np.array([('2001-01-01', 1.)],
                           dtype=[('', '|S10'), ('', float)])
        assert_equal(test, control)


    def test_spacedelimiter(self):
        "Test space delimiter"
        data = StringIO("1  2  3  4   5\n6  7  8  9  10")
        test = np.ndfromtxt(data)
        control = np.array([[ 1., 2., 3., 4., 5.],
                            [ 6., 7., 8., 9., 10.]])
        assert_equal(test, control)

    def test_integer_delimiter(self):
        "Test using an integer for delimiter"
        data = "  1  2  3\n  4  5 67\n890123  4"
        test = np.genfromtxt(StringIO(data), delimiter=3)
        control = np.array([[1, 2, 3], [4, 5, 67], [890, 123, 4]])
        assert_equal(test, control)


    def test_missing(self):
        data = StringIO('1,2,3,,5\n')
        test = np.ndfromtxt(data, dtype=int, delimiter=',', \
                            converters={3:lambda s: int(s or - 999)})
        control = np.array([1, 2, 3, -999, 5], int)
        assert_equal(test, control)


    def test_missing_with_tabs(self):
        "Test w/ a delimiter tab"
        txt = "1\t2\t3\n\t2\t\n1\t\t3"
        test = np.genfromtxt(StringIO(txt), delimiter="\t",
                             usemask=True,)
        ctrl_d = np.array([(1, 2, 3), (np.nan, 2, np.nan), (1, np.nan, 3)],)
        ctrl_m = np.array([(0, 0, 0), (1, 0, 1), (0, 1, 0)], dtype=bool)
        assert_equal(test.data, ctrl_d)
        assert_equal(test.mask, ctrl_m)


    def test_usecols(self):
        "Test the selection of columns"
        # Select 1 column
        control = np.array([[1, 2], [3, 4]], float)
        data = StringIO()
        np.savetxt(data, control)
        data.seek(0)
        test = np.ndfromtxt(data, dtype=float, usecols=(1,))
        assert_equal(test, control[:, 1])
        #
        control = np.array([[1, 2, 3], [3, 4, 5]], float)
        data = StringIO()
        np.savetxt(data, control)
        data.seek(0)
        test = np.ndfromtxt(data, dtype=float, usecols=(1, 2))
        assert_equal(test, control[:, 1:])
        # Testing with arrays instead of tuples.
        data.seek(0)
        test = np.ndfromtxt(data, dtype=float, usecols=np.array([1, 2]))
        assert_equal(test, control[:, 1:])

    def test_usecols_as_css(self):
        "Test giving usecols with a comma-separated string"
        data = "1 2 3\n4 5 6"
        test = np.genfromtxt(StringIO(data),
                             names="a, b, c", usecols="a, c")
        ctrl = np.array([(1, 3), (4, 6)], dtype=[(_, float) for _ in "ac"])
        assert_equal(test, ctrl)

    def test_usecols_with_structured_dtype(self):
        "Test usecols with an explicit structured dtype"
        data = StringIO("""JOE 70.1 25.3\nBOB 60.5 27.9""")
        names = ['stid', 'temp']
        dtypes = ['S4', 'f8']
        test = np.ndfromtxt(data, usecols=(0, 2), dtype=list(zip(names, dtypes)))
        assert_equal(test['stid'], asbytes_nested(["JOE", "BOB"]))
        assert_equal(test['temp'], [25.3, 27.9])

    def test_usecols_with_integer(self):
        "Test usecols with an integer"
        test = np.genfromtxt(StringIO("1 2 3\n4 5 6"), usecols=0)
        assert_equal(test, np.array([1., 4.]))

    def test_usecols_with_named_columns(self):
        "Test usecols with named columns"
        ctrl = np.array([(1, 3), (4, 6)], dtype=[('a', float), ('c', float)])
        data = "1 2 3\n4 5 6"
        kwargs = dict(names="a, b, c")
        test = np.genfromtxt(StringIO(data), usecols=(0, -1), **kwargs)
        assert_equal(test, ctrl)
        test = np.genfromtxt(StringIO(data),
                             usecols=('a', 'c'), **kwargs)
        assert_equal(test, ctrl)

    def test_empty_file(self):
        "Test that an empty file raises the proper warning."
        warn_ctx = WarningManager()
        warn_ctx.__enter__()
        try:
            warnings.filterwarnings("ignore", message="genfromtxt: Empty input file:")
            data = StringIO()
            test = np.genfromtxt(data)
            assert_equal(test, np.array([]))
        finally:
            warn_ctx.__exit__()


    def test_fancy_dtype_alt(self):
        "Check that a nested dtype isn't MIA"
        data = StringIO('1,2,3.0\n4,5,6.0\n')
        fancydtype = np.dtype([('x', int), ('y', [('t', int), ('s', float)])])
        test = np.mafromtxt(data, dtype=fancydtype, delimiter=',')
        control = ma.array([(1, (2, 3.0)), (4, (5, 6.0))], dtype=fancydtype)
        assert_equal(test, control)


    def test_shaped_dtype(self):
        c = StringIO("aaaa  1.0  8.0  1 2 3 4 5 6")
        dt = np.dtype([('name', 'S4'), ('x', float), ('y', float),
                       ('block', int, (2, 3))])
        x = np.ndfromtxt(c, dtype=dt)
        a = np.array([('aaaa', 1.0, 8.0, [[1, 2, 3], [4, 5, 6]])],
                     dtype=dt)
        assert_array_equal(x, a)

    def test_withmissing(self):
        data = StringIO('A,B\n0,1\n2,N/A')
        kwargs = dict(delimiter=",", missing_values="N/A", names=True)
        test = np.mafromtxt(data, dtype=None, **kwargs)
        control = ma.array([(0, 1), (2, -1)],
                           mask=[(False, False), (False, True)],
                           dtype=[('A', np.int), ('B', np.int)])
        assert_equal(test, control)
        assert_equal(test.mask, control.mask)
        #
        data.seek(0)
        test = np.mafromtxt(data, **kwargs)
        control = ma.array([(0, 1), (2, -1)],
                           mask=[(False, False), (False, True)],
                           dtype=[('A', np.float), ('B', np.float)])
        assert_equal(test, control)
        assert_equal(test.mask, control.mask)


    def test_user_missing_values(self):
        data = "A, B, C\n0, 0., 0j\n1, N/A, 1j\n-9, 2.2, N/A\n3, -99, 3j"
        basekwargs = dict(dtype=None, delimiter=",", names=True,)
        mdtype = [('A', int), ('B', float), ('C', complex)]
        #
        test = np.mafromtxt(StringIO(data), missing_values="N/A",
                            **basekwargs)
        control = ma.array([(0, 0.0, 0j), (1, -999, 1j),
                            (-9, 2.2, -999j), (3, -99, 3j)],
                            mask=[(0, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)],
                            dtype=mdtype)
        assert_equal(test, control)
        #
        basekwargs['dtype'] = mdtype
        test = np.mafromtxt(StringIO(data),
                            missing_values={0:-9, 1:-99, 2:-999j}, **basekwargs)
        control = ma.array([(0, 0.0, 0j), (1, -999, 1j),
                            (-9, 2.2, -999j), (3, -99, 3j)],
                            mask=[(0, 0, 0), (0, 1, 0), (1, 0, 1), (0, 1, 0)],
                            dtype=mdtype)
        assert_equal(test, control)
        #
        test = np.mafromtxt(StringIO(data),
                            missing_values={0:-9, 'B':-99, 'C':-999j},
                            **basekwargs)
        control = ma.array([(0, 0.0, 0j), (1, -999, 1j),
                            (-9, 2.2, -999j), (3, -99, 3j)],
                            mask=[(0, 0, 0), (0, 1, 0), (1, 0, 1), (0, 1, 0)],
                            dtype=mdtype)
        assert_equal(test, control)

    def test_user_filling_values(self):
        "Test with missing and filling values"
        ctrl = np.array([(0, 3), (4, -999)], dtype=[('a', int), ('b', int)])
        data = "N/A, 2, 3\n4, ,???"
        kwargs = dict(delimiter=",",
                      dtype=int,
                      names="a,b,c",
                      missing_values={0:"N/A", 'b':" ", 2:"???"},
                      filling_values={0:0, 'b':0, 2:-999})
        test = np.genfromtxt(StringIO(data), **kwargs)
        ctrl = np.array([(0, 2, 3), (4, 0, -999)],
                        dtype=[(_, int) for _ in "abc"])
        assert_equal(test, ctrl)
        #
        test = np.genfromtxt(StringIO(data), usecols=(0, -1), **kwargs)
        ctrl = np.array([(0, 3), (4, -999)], dtype=[(_, int) for _ in "ac"])
        assert_equal(test, ctrl)


    def test_withmissing_float(self):
        data = StringIO('A,B\n0,1.5\n2,-999.00')
        test = np.mafromtxt(data, dtype=None, delimiter=',',
                            missing_values='-999.0', names=True,)
        control = ma.array([(0, 1.5), (2, -1.)],
                           mask=[(False, False), (False, True)],
                           dtype=[('A', np.int), ('B', np.float)])
        assert_equal(test, control)
        assert_equal(test.mask, control.mask)


    def test_with_masked_column_uniform(self):
        "Test masked column"
        data = StringIO('1 2 3\n4 5 6\n')
        test = np.genfromtxt(data, dtype=None,
                             missing_values='2,5', usemask=True)
        control = ma.array([[1, 2, 3], [4, 5, 6]], mask=[[0, 1, 0], [0, 1, 0]])
        assert_equal(test, control)

    def test_with_masked_column_various(self):
        "Test masked column"
        data = StringIO('True 2 3\nFalse 5 6\n')
        test = np.genfromtxt(data, dtype=None,
                             missing_values='2,5', usemask=True)
        control = ma.array([(1, 2, 3), (0, 5, 6)],
                           mask=[(0, 1, 0), (0, 1, 0)],
                           dtype=[('f0', bool), ('f1', bool), ('f2', int)])
        assert_equal(test, control)


    def test_invalid_raise(self):
        "Test invalid raise"
        data = ["1, 1, 1, 1, 1"] * 50
        for i in range(5):
            data[10 * i] = "2, 2, 2, 2 2"
        data.insert(0, "a, b, c, d, e")
        mdata = StringIO("\n".join(data))
        #
        kwargs = dict(delimiter=",", dtype=None, names=True)
        # XXX: is there a better way to get the return value of the callable in
        # assert_warns ?
        ret = {}
        def f(_ret={}):
            _ret['mtest'] = np.ndfromtxt(mdata, invalid_raise=False, **kwargs)
        assert_warns(ConversionWarning, f, _ret=ret)
        mtest = ret['mtest']
        assert_equal(len(mtest), 45)
        assert_equal(mtest, np.ones(45, dtype=[(_, int) for _ in 'abcde']))
        #
        mdata.seek(0)
        assert_raises(ValueError, np.ndfromtxt, mdata,
                      delimiter=",", names=True)

    def test_invalid_raise_with_usecols(self):
        "Test invalid_raise with usecols"
        data = ["1, 1, 1, 1, 1"] * 50
        for i in range(5):
            data[10 * i] = "2, 2, 2, 2 2"
        data.insert(0, "a, b, c, d, e")
        mdata = StringIO("\n".join(data))
        kwargs = dict(delimiter=",", dtype=None, names=True,
                      invalid_raise=False)
        # XXX: is there a better way to get the return value of the callable in
        # assert_warns ?
        ret = {}
        def f(_ret={}):
            _ret['mtest'] = np.ndfromtxt(mdata, usecols=(0, 4), **kwargs)
        assert_warns(ConversionWarning, f, _ret=ret)
        mtest = ret['mtest']
        assert_equal(len(mtest), 45)
        assert_equal(mtest, np.ones(45, dtype=[(_, int) for _ in 'ae']))
        #
        mdata.seek(0)
        mtest = np.ndfromtxt(mdata, usecols=(0, 1), **kwargs)
        assert_equal(len(mtest), 50)
        control = np.ones(50, dtype=[(_, int) for _ in 'ab'])
        control[[10 * _ for _ in range(5)]] = (2, 2)
        assert_equal(mtest, control)


    def test_inconsistent_dtype(self):
        "Test inconsistent dtype"
        data = ["1, 1, 1, 1, -1.1"] * 50
        mdata = StringIO("\n".join(data))

        converters = {4: lambda x:"(%s)" % x}
        kwargs = dict(delimiter=",", converters=converters,
                      dtype=[(_, int) for _ in 'abcde'],)
        assert_raises(ValueError, np.genfromtxt, mdata, **kwargs)


    def test_default_field_format(self):
        "Test default format"
        data = "0, 1, 2.3\n4, 5, 6.7"
        mtest = np.ndfromtxt(StringIO(data),
                             delimiter=",", dtype=None, defaultfmt="f%02i")
        ctrl = np.array([(0, 1, 2.3), (4, 5, 6.7)],
                        dtype=[("f00", int), ("f01", int), ("f02", float)])
        assert_equal(mtest, ctrl)

    def test_single_dtype_wo_names(self):
        "Test single dtype w/o names"
        data = "0, 1, 2.3\n4, 5, 6.7"
        mtest = np.ndfromtxt(StringIO(data),
                             delimiter=",", dtype=float, defaultfmt="f%02i")
        ctrl = np.array([[0., 1., 2.3], [4., 5., 6.7]], dtype=float)
        assert_equal(mtest, ctrl)

    def test_single_dtype_w_explicit_names(self):
        "Test single dtype w explicit names"
        data = "0, 1, 2.3\n4, 5, 6.7"
        mtest = np.ndfromtxt(StringIO(data),
                             delimiter=",", dtype=float, names="a, b, c")
        ctrl = np.array([(0., 1., 2.3), (4., 5., 6.7)],
                        dtype=[(_, float) for _ in "abc"])
        assert_equal(mtest, ctrl)

    def test_single_dtype_w_implicit_names(self):
        "Test single dtype w implicit names"
        data = "a, b, c\n0, 1, 2.3\n4, 5, 6.7"
        mtest = np.ndfromtxt(StringIO(data),
                             delimiter=",", dtype=float, names=True)
        ctrl = np.array([(0., 1., 2.3), (4., 5., 6.7)],
                        dtype=[(_, float) for _ in "abc"])
        assert_equal(mtest, ctrl)

    def test_easy_structured_dtype(self):
        "Test easy structured dtype"
        data = "0, 1, 2.3\n4, 5, 6.7"
        mtest = np.ndfromtxt(StringIO(data), delimiter=",",
                             dtype=(int, float, float), defaultfmt="f_%02i")
        ctrl = np.array([(0, 1., 2.3), (4, 5., 6.7)],
                        dtype=[("f_00", int), ("f_01", float), ("f_02", float)])
        assert_equal(mtest, ctrl)

    def test_autostrip(self):
        "Test autostrip"
        data = "01/01/2003  , 1.3,   abcde"
        kwargs = dict(delimiter=",", dtype=None)
        mtest = np.ndfromtxt(StringIO(data), **kwargs)
        ctrl = np.array([('01/01/2003  ', 1.3, '   abcde')],
                        dtype=[('f0', '|S12'), ('f1', float), ('f2', '|S8')])
        assert_equal(mtest, ctrl)
        mtest = np.ndfromtxt(StringIO(data), autostrip=True, **kwargs)
        ctrl = np.array([('01/01/2003', 1.3, 'abcde')],
                        dtype=[('f0', '|S10'), ('f1', float), ('f2', '|S5')])
        assert_equal(mtest, ctrl)

    def test_replace_space(self):
        "Test the 'replace_space' option"
        txt = "A.A, B (B), C:C\n1, 2, 3.14"
        # Test default: replace ' ' by '_' and delete non-alphanum chars
        test = np.genfromtxt(StringIO(txt),
                             delimiter=",", names=True, dtype=None)
        ctrl_dtype = [("AA", int), ("B_B", int), ("CC", float)]
        ctrl = np.array((1, 2, 3.14), dtype=ctrl_dtype)
        assert_equal(test, ctrl)
        # Test: no replace, no delete
        test = np.genfromtxt(StringIO(txt),
                             delimiter=",", names=True, dtype=None,
                             replace_space='', deletechars='')
        ctrl_dtype = [("A.A", int), ("B (B)", int), ("C:C", float)]
        ctrl = np.array((1, 2, 3.14), dtype=ctrl_dtype)
        assert_equal(test, ctrl)
        # Test: no delete (spaces are replaced by _)
        test = np.genfromtxt(StringIO(txt),
                             delimiter=",", names=True, dtype=None,
                             deletechars='')
        ctrl_dtype = [("A.A", int), ("B_(B)", int), ("C:C", float)]
        ctrl = np.array((1, 2, 3.14), dtype=ctrl_dtype)
        assert_equal(test, ctrl)

    def test_incomplete_names(self):
        "Test w/ incomplete names"
        data = "A,,C\n0,1,2\n3,4,5"
        kwargs = dict(delimiter=",", names=True)
        # w/ dtype=None
        ctrl = np.array([(0, 1, 2), (3, 4, 5)],
                        dtype=[(_, int) for _ in ('A', 'f0', 'C')])
        test = np.ndfromtxt(StringIO(data), dtype=None, **kwargs)
        assert_equal(test, ctrl)
        # w/ default dtype
        ctrl = np.array([(0, 1, 2), (3, 4, 5)],
                        dtype=[(_, float) for _ in ('A', 'f0', 'C')])
        test = np.ndfromtxt(StringIO(data), **kwargs)

    def test_names_auto_completion(self):
        "Make sure that names are properly completed"
        data = "1 2 3\n 4 5 6"
        test = np.genfromtxt(StringIO(data),
                             dtype=(int, float, int), names="a")
        ctrl = np.array([(1, 2, 3), (4, 5, 6)],
                        dtype=[('a', int), ('f0', float), ('f1', int)])
        assert_equal(test, ctrl)

    def test_names_with_usecols_bug1636(self):
        "Make sure we pick up the right names w/ usecols"
        data = "A,B,C,D,E\n0,1,2,3,4\n0,1,2,3,4\n0,1,2,3,4"
        ctrl_names = ("A", "C", "E")
        test = np.genfromtxt(StringIO(data),
                             dtype=(int, int, int), delimiter=",",
                             usecols=(0, 2, 4), names=True)
        assert_equal(test.dtype.names, ctrl_names)
        #
        test = np.genfromtxt(StringIO(data),
                             dtype=(int, int, int), delimiter=",",
                             usecols=("A", "C", "E"), names=True)
        assert_equal(test.dtype.names, ctrl_names)
        #
        test = np.genfromtxt(StringIO(data),
                             dtype=int, delimiter=",",
                             usecols=("A", "C", "E"), names=True)
        assert_equal(test.dtype.names, ctrl_names)



    def test_fixed_width_names(self):
        "Test fix-width w/ names"
        data = "    A    B   C\n    0    1 2.3\n   45   67   9."
        kwargs = dict(delimiter=(5, 5, 4), names=True, dtype=None)
        ctrl = np.array([(0, 1, 2.3), (45, 67, 9.)],
                        dtype=[('A', int), ('B', int), ('C', float)])
        test = np.ndfromtxt(StringIO(data), **kwargs)
        assert_equal(test, ctrl)
        #
        kwargs = dict(delimiter=5, names=True, dtype=None)
        ctrl = np.array([(0, 1, 2.3), (45, 67, 9.)],
                        dtype=[('A', int), ('B', int), ('C', float)])
        test = np.ndfromtxt(StringIO(data), **kwargs)
        assert_equal(test, ctrl)

    def test_filling_values(self):
        "Test missing values"
        data = "1, 2, 3\n1, , 5\n0, 6, \n"
        kwargs = dict(delimiter=",", dtype=None, filling_values= -999)
        ctrl = np.array([[1, 2, 3], [1, -999, 5], [0, 6, -999]], dtype=int)
        test = np.ndfromtxt(StringIO(data), **kwargs)
        assert_equal(test, ctrl)


    def test_recfromtxt(self):
        #
        data = StringIO('A,B\n0,1\n2,3')
        kwargs = dict(delimiter=",", missing_values="N/A", names=True)
        test = np.recfromtxt(data, **kwargs)
        control = np.array([(0, 1), (2, 3)],
                           dtype=[('A', np.int), ('B', np.int)])
        self.assertTrue(isinstance(test, np.recarray))
        assert_equal(test, control)
        #
        data = StringIO('A,B\n0,1\n2,N/A')
        test = np.recfromtxt(data, dtype=None, usemask=True, **kwargs)
        control = ma.array([(0, 1), (2, -1)],
                           mask=[(False, False), (False, True)],
                           dtype=[('A', np.int), ('B', np.int)])
        assert_equal(test, control)
        assert_equal(test.mask, control.mask)
        assert_equal(test.A, [0, 2])


    def test_recfromcsv(self):
        #
        data = StringIO('A,B\n0,1\n2,3')
        kwargs = dict(missing_values="N/A", names=True, case_sensitive=True)
        test = np.recfromcsv(data, dtype=None, **kwargs)
        control = np.array([(0, 1), (2, 3)],
                           dtype=[('A', np.int), ('B', np.int)])
        self.assertTrue(isinstance(test, np.recarray))
        assert_equal(test, control)
        #
        data = StringIO('A,B\n0,1\n2,N/A')
        test = np.recfromcsv(data, dtype=None, usemask=True, **kwargs)
        control = ma.array([(0, 1), (2, -1)],
                           mask=[(False, False), (False, True)],
                           dtype=[('A', np.int), ('B', np.int)])
        assert_equal(test, control)
        assert_equal(test.mask, control.mask)
        assert_equal(test.A, [0, 2])
        #
        data = StringIO('A,B\n0,1\n2,3')
        test = np.recfromcsv(data, missing_values='N/A',)
        control = np.array([(0, 1), (2, 3)],
                           dtype=[('a', np.int), ('b', np.int)])
        self.assertTrue(isinstance(test, np.recarray))
        assert_equal(test, control)

    def test_gft_filename(self):
        # Test that we can load data from a filename as well as a file object
        data = '0 1 2\n3 4 5'
        exp_res = np.arange(6).reshape((2,3))
        assert_array_equal(np.genfromtxt(StringIO(data)), exp_res)
        f, name = mkstemp()
        # Thanks to another windows brokeness, we can't use
        # NamedTemporaryFile: a file created from this function cannot be
        # reopened by another open call. So we first put the string
        # of the test reference array, write it to a securely opened file,
        # which is then read from by the loadtxt function
        try:
            os.write(f, asbytes(data))
            assert_array_equal(np.genfromtxt(name), exp_res)
        finally:
            os.close(f)
            os.unlink(name)

    def test_gft_generator_source(self):
        def count():
            for i in range(10):
                yield asbytes("%d" % i)

        res = np.genfromtxt(count())
        assert_array_equal(res, np.arange(10))


def test_gzip_load():
    a = np.random.random((5, 5))

    s = StringIO()
    f = gzip.GzipFile(fileobj=s, mode="w")

    np.save(f, a)
    f.close()
    s.seek(0)

    f = gzip.GzipFile(fileobj=s, mode="r")
    assert_array_equal(np.load(f), a)


def test_gzip_loadtxt():
    # Thanks to another windows brokeness, we can't use
    # NamedTemporaryFile: a file created from this function cannot be
    # reopened by another open call. So we first put the gzipped string
    # of the test reference array, write it to a securely opened file,
    # which is then read from by the loadtxt function
    s = StringIO()
    g = gzip.GzipFile(fileobj=s, mode='w')
    g.write(asbytes('1 2 3\n'))
    g.close()
    s.seek(0)

    f, name = mkstemp(suffix='.gz')
    try:
        os.write(f, s.read())
        s.close()
        assert_array_equal(np.loadtxt(name), [1, 2, 3])
    finally:
        os.close(f)
        os.unlink(name)

def test_gzip_loadtxt_from_string():
    s = StringIO()
    f = gzip.GzipFile(fileobj=s, mode="w")
    f.write(asbytes('1 2 3\n'))
    f.close()
    s.seek(0)

    f = gzip.GzipFile(fileobj=s, mode="r")
    assert_array_equal(np.loadtxt(f), [1, 2, 3])

def test_npzfile_dict():
    s = StringIO()
    x = np.zeros((3, 3))
    y = np.zeros((3, 3))

    np.savez(s, x=x, y=y)
    s.seek(0)

    z = np.load(s)

    assert 'x' in z
    assert 'y' in z
    assert 'x' in list(z.keys())
    assert 'y' in list(z.keys())

    for f, a in z.items():
        assert f in ['x', 'y']
        assert_equal(a.shape, (3, 3))

    assert len(list(z.items())) == 2

    for f in z:
        assert f in ['x', 'y']

    assert 'x' in list(z.keys())

def test_load_refcount():
    # Check that objects returned by np.load are directly freed based on
    # their refcount, rather than needing the gc to collect them.

    f = StringIO()
    np.savez(f, [1, 2, 3])
    f.seek(0)

    gc.collect()
    n_before = len(gc.get_objects())
    np.load(f)
    n_after = len(gc.get_objects())

    assert_equal(n_before, n_after)

if __name__ == "__main__":
    run_module_suite()
