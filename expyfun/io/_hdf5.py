# -*- coding: utf-8 -*-
"""HDF5 saving functions
"""

import numpy as np
from os import path as op

from .._utils import _check_pytables, string_types


##############################################################################
# WRITE

def write_hdf5(fname, data, overwrite=False):
    """Write python object to HDF5 format using Pytables

    Parameters
    ----------
    fname : str
        Filename to use.
    data : object
        Object to write. Can be of any of these types:
            {ndarray, dict, list, tuple, int, float, str}
        Note that dict objects must only have ``str`` keys.
    overwrite : bool
        If True, overwrite file (if it exists).
    """
    tb = _check_pytables()
    if op.isfile(fname) and not overwrite:
        raise IOError('file "%s" exists, use overwrite=True to overwrite'
                      % fname)
    if not isinstance(data, dict):
        raise TypeError('data must be a dict')
    o_f = tb.open_file if hasattr(tb, 'open_file') else tb.openFile
    with o_f(fname, mode='w') as fid:
        if hasattr(fid, 'create_group'):
            c_g = fid.create_group
            c_t = fid.create_table
            c_c_a = fid.create_carray
        else:
            c_g = fid.createGroup
            c_t = fid.createTable
            c_c_a = fid.createCArray
        filters = tb.Filters(complib='zlib', complevel=5)
        write_params = (c_g, c_t, c_c_a, filters)
        _triage_write('expyfun', data, fid.root, *write_params)


def _triage_write(key, value, root, *write_params):
    tb = _check_pytables()
    create_group, create_table, create_c_array, filters = write_params
    if isinstance(value, dict):
        sub_root = create_group(root, key, 'dict')
        for key, sub_value in value.items():
            if not isinstance(key, string_types):
                raise TypeError('All dict keys must be strings')
            _triage_write('key{0}'.format(key), sub_value, sub_root,
                          *write_params)
    elif isinstance(value, (list, tuple)):
        title = 'list' if isinstance(value, list) else 'tuple'
        sub_root = create_group(root, key, title)
        for vi, sub_value in enumerate(value):
            _triage_write('idx{0}'.format(vi), sub_value, sub_root,
                          *write_params)
    elif isinstance(value, (int, float, str)):
        if isinstance(value, int):
            title = 'int'
        elif isinstance(value, float):
            title = 'float'
        else:
            title = 'str'
        value = np.atleast_1d(value)
        atom = tb.Atom.from_dtype(value.dtype)
        s = create_c_array(root, key, atom, (1,),
                           title=title, filters=filters)
        s[:] = value
    elif isinstance(value, np.ndarray):
        atom = tb.Atom.from_dtype(value.dtype)
        s = create_c_array(root, key, atom, value.shape,
                           title='ndarray', filters=filters)
        s[:] = value
    else:
        raise TypeError('unsupported type %s' % type(value))


##############################################################################
# READ

def read_hdf5(fname):
    """Read python object from HDF5 format using Pytables

    Parameters
    ----------
    fname : str
        File to load.

    Returns
    -------
    data : object
        The loaded data. Can be of any type supported by ``write_hdf5``.
    """
    tb = _check_pytables()
    if not op.isfile(fname):
        raise IOError('file "%s" not found' % fname)
    o_f = tb.open_file if hasattr(tb, 'open_file') else tb.openFile
    with o_f(fname, mode='r') as fid:
        if not hasattr(fid.root, 'expyfun'):
            raise TypeError('no expyfun data found')
        data = _triage_read(fid.root.expyfun)
    return data


def _triage_read(node):
    tb = _check_pytables()
    type_str = node._v_title
    if isinstance(node, tb.Group):
        if type_str == 'dict':
            data = dict()
            for subnode in node:
                key = subnode._v_name[3:]  # cut off "idx" or "key" prefix
                data[key] = _triage_read(subnode)
        elif type_str in ['list', 'tuple']:
            data = list()
            ii = 0
            while True:
                subnode = getattr(node, 'idx{0}'.format(ii), None)
                if subnode is None:
                    break
                data.append(_triage_read(subnode))
                ii += 1
            assert len(data) == ii
            data = tuple(data) if type_str == 'tuple' else data
            return data
        else:
            raise NotImplementedError('Unknown group type: {0}'
                                      ''.format(type_str))
    elif type_str == 'ndarray':
        data = np.array(node)
    elif type_str in ('int', 'float', 'str'):
        if type_str == 'int':
            cast = int
        elif type_str == 'float':
            cast = float
        else:
            cast = str
        data = cast(np.array(node)[0])
    else:
        raise TypeError('Unknown node type: {0}'.format(type_str))
    return data
