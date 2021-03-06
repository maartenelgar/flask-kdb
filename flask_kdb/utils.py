__all__ = ['qList_to_pd_series', 'qtable_to_dataframe', 'qTempList_to_pd_tseries', 'get_q_status', 'convert_qdata']

from collections import OrderedDict

import pandas
import numpy

from qpython.qcollection import QTable, QKeyedTable, QDictionary, QList, QTemporalList
from qpython.qtype import qnull, QMONTH, QDATE, QDATETIME, QMINUTE, QSECOND, QTIME, QTIMESTAMP, QTIMESPAN, QNULLMAP

_EPOCH_QMONTH = numpy.timedelta64(360, 'M')
_EPOCH_QDATE = numpy.timedelta64(10957, 'D')
_EPOCH_QDATETIME = numpy.timedelta64(946684800000, 'ms')
_EPOCH_TIMESTAMP = numpy.timedelta64(946684800000000000, 'ns')

_QMONTH_NULL = qnull(QMONTH)
_QDATE_NULL = qnull(QDATE)
_QDATETIME_NULL = qnull(QDATETIME)
_QMINUTE_NULL = qnull(QMINUTE)
_QSECOND_NULL = qnull(QSECOND)
_QTIME_NULL = qnull(QTIME)
_QTIMESTAMP_NULL = qnull(QTIMESTAMP)
_QTIMESPAN_NULL = qnull(QTIMESPAN)


def qtable_to_dataframe(q_table):
    """
    Converts a QTable into a pandas.DataFrame with type level conversions occurring as well:
        dates -> datetime64 w/ qnulls replaces with NaT's
        times -> timedelta64 w/ qnulls replaces with NaT's
        other types -> qnulls replaced with NaN's


    >>> data = q('trade:([]date:`date$();time:`time$();sym:`symbol$();price:`float$();size:`int$())')
    >>> data = q('`trade insert(2000.01.01;00:00:00.000;`a;10.75;100)')
    >>> data = q('`trade insert(0Nd;0Nt;`;0n;0N)')
    >>> data = q('trade')
    >>> print qtable_to_dataframe(data)
            date   time  sym  price  size
    0 2000-01-01 0 days    a  10.75   100
    1        NaT    NaT  NaN    NaN   NaN


    >>> data = q('kt:(flip (enlist `eid)!enlist 0n 1002)!flip `name`iq!(`Dent`Beeblebrox;98 42)')
    >>> data = q('kt')
    >>> print qtable_to_dataframe(data)
                 name  iq
    eid
    NaN          Dent  98
     1002  Beeblebrox  42


    >>> data = q('ktc:([lname:`Dent``Prefect; fname:`Arthur`Zaphod`]; iq:98 42 126)')
    >>> data = q('ktc')
    >>> print qtable_to_dataframe(data)
                     iq
    lname   fname
    Dent    Arthur   98
    NaN     Zaphod   42
    Prefect NaN     126

    :param q_table: Input qTable
    :return: pandas.DataFrame
    :raises TypeError: Only QTable and QKeyedTable are supported
    """
    if isinstance(q_table, QTable):
        cols = _qtable_to_series_odict(q_table)
        df = pandas.DataFrame(cols)
    elif isinstance(q_table, QKeyedTable) or isinstance(q_table, QDictionary):
        cols = _qtable_to_series_odict(q_table.values)
        cols.update(_qtable_to_series_odict(q_table.keys))
        # For now, this seems to be the best option for dealing with keyed tables...
        # Basically you stuff all of the columns inpt the main frame and set the
        # keyed columns to be the index. This allow for the trivial addition of
        # multiple same level indexes
        df = pandas.DataFrame(cols).set_index([i for i in q_table.keys.dtype.names])
    else:
        raise ValueError('Only QTable and QKeyedTable are supported')

    # Converted Dataframe
    return df


def _qtable_to_series_odict(q_table):
    # Converted Series Columns
    """
    Utility function for qtable_to_dataframe
    This has no type awareness for QKeyedTables vs QTables -- assumes everything is a QTable
    :param q_table: Input Table
    :return: OrderedDict of converted columns
    """
    cols = OrderedDict()
    for col in q_table.dtype.names:
        q_type = q_table.meta[col]
        if q_type in [QMINUTE, QSECOND, QTIME, QTIMESPAN, QMONTH, QDATE, QDATETIME, QTIMESTAMP]:
            cols[col] = qTempList_to_pd_tseries(q_table[col], q_type)
        else:
            cols[col] = qList_to_pd_series(q_table[col], q_type)

    return cols


def qTempList_to_pd_tseries(q_list, q_type):
    """
    Returns new converted pandas.TimeSeries using q_lists data. qnulls will be replaced with NaT
    This function may take any q temporal type as an input and as such will return the appropriate series of either
    timedelta64's or datetime64's

    :param q_list: Input Data
    :param q_type: Input Data's q_type
    :return: pandas.TimeSeries
    :raise TypeError: input datatype was not a qtemporal
    """
    offset = None
    if q_type == QTIMESTAMP:
        res = 'ns'
        offset = _EPOCH_TIMESTAMP
    elif q_type == QDATE:
        res = 'D'
        offset = _EPOCH_QDATE
    elif q_type == QMONTH:
        res = 'M'
        offset = _EPOCH_QMONTH
    elif q_type == QDATETIME:
        res = 'ms'
        offset = _EPOCH_QDATETIME
    elif q_type == QTIME:
        res = 'ms'
    elif q_type == QMINUTE:
        res = 'm'
    elif q_type == QSECOND:
        res = 's'
    elif q_type == QTIMESPAN:
        res = 'ns'
    else:
        raise TypeError("invalid q_type submitted: {}".format(q_type))

    if offset:
        dtype = 'datetime64[{}]'.format(res)
        null_val = numpy.datetime64('NaT')
    else:
        null_val = numpy.timedelta64('NaT')
        dtype = 'timedelta64[{}]'.format(res)

    null_func = QNULLMAP[q_type][2]
    nulls = null_func(q_list)

    out = numpy.empty_like(q_list, dtype=dtype)
    out[~nulls] = q_list[~nulls].astype(dtype)
    if offset:
        out[~nulls] += offset
    out[nulls] = null_val

    return pandas.TimeSeries(data=out)


def qList_to_pd_series(q_list, q_type):
    """
    Returns a new pandas.Series from q_list with values converted from qulls to NaN

    :param q_list: Input data
    :param q_type: q_lists original q_type
    :return: pandas.Series w/ nan's for qnulls
    """
    null = QNULLMAP[q_type][1]

    return pandas.Series(data=q_list).replace(null, numpy.NaN)


def get_q_status(q_conn):
    status = (
        ('Is Connected', str(q_conn.is_connected())),
        ('Protocol Version', str(q_conn.protocol_version)),
        ('Host', str(q_conn.host)),
        ('Port', str(q_conn.port)),
        ('Timeout', str(q_conn.timeout))
    )
    return status


def convert_qdata(data):
    if isinstance(data, QTable) or isinstance(data, QKeyedTable) or isinstance(data, QDictionary):
        html = qtable_to_html(data)
    elif isinstance(data, QList):
        html = "<samp>{}</samp>".format(str(data.tolist()))
    elif isinstance(data, QTemporalList):
        html = "<samp>{}</samp>".format(str(convert_qtemporal(data)))
    else:
        html = "<samp>{}</samp>".format(str(data))
    return html


def convert_qtemporal(data):
    sane = [str(i.raw) for i in data]
    return sane


def qtable_to_html(q_table):
    html = qtable_to_dataframe(q_table).to_html(
        max_rows=100, escape=False).replace('border="1" class="dataframe"', 'class="table table-striped"')
    return html