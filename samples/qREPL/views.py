from flask import render_template, request, redirect, session
from flask_kdb import get_kdb
from . import app
from qpython.qcollection import QTable, QKeyedTable, QList, QDictionary, QTemporalList
from pandas import DataFrame


@app.before_first_request
def set_query():
    session['query'] = None


@app.route("/", methods=['GET'])
def display_ide():
    q_conn = get_kdb()
    qstatus = get_q_status(q_conn)
    if session['query']:
        return render_template('query.html', **session['query'])
    else:
        session['query'] = None
        return render_template('base.html', qstatus=qstatus, orig_query=None)


@app.route("/run_query", methods=['POST'])
def run_query():
    q_conn = get_kdb()
    qstatus = get_q_status(q_conn)
    orig_query = request.form['queryText']
    query = orig_query.encode('ascii').replace('\n', ' ').replace('\r', '').replace('  ', ' ')
    data = q_conn(query)
    data = convert_qdata(data)
    session['query'] = dict(qstatus=qstatus, orig_query=orig_query, query=query, query_result=data)
    return redirect('/')


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
    if isinstance(data, QTable):
        html = qtable_to_html(data)
    elif isinstance(data, QKeyedTable) or isinstance(data, QDictionary):
        html = qtable_to_html(data.values, keys=data.keys)
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


def qtable_to_html(values, keys=None):
    html = DataFrame(values, index=keys).to_html(
        max_rows=100, escape=False).replace('border="1" class="dataframe"', 'class="table table-striped"')
    return html
