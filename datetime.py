#!python
#Copyright 2015 Mark Santesson
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

# To make this run more easily in windows, add the file into the path
# and make sure that *.py files are associated with python:
#   C:\>assoc .PY=Python.File
#   C:\>ftype Python.File=c:\Python27\Python.exe "%1" %*


# This is to develop/verify/unittest the datetime conversion page.


import calendar
import copy
import datetime
import time
import pytz
import re
import xml.dom.minidom
import xml.etree.ElementTree as ET

from   datetime import datetime


localtz = pytz.timezone('US/Central')
othertz = pytz.timezone('US/Eastern')


class Bank(object):
    def __init__(self, name, cmp_fn, str_fn, now_fn, *args):
        self.name        = name
        self.str         = str_fn
        self.cmp_fn      = cmp_fn
        self.now_fn      = now_fn
        self.conversions = args # Conversion fn going *from* another time rep.
        self.now         = self.now_fn()


Banks = [ Bank( 'Timezone Naive Datetime Local'
              , lambda l,r: abs((r-l).total_seconds()) < 1
              , lambda dt: str(dt)
              , lambda: datetime.now()
              , None
              , lambda dt: pytz.utc.localize(dt).astimezone(localtz).replace(tzinfo=None)
              , lambda dt: dt.astimezone(localtz).replace(tzinfo=None)
              , lambda t: datetime(*t[:6])
              , lambda t: pytz.utc.localize(datetime(*t[:6])).astimezone(localtz).replace(tzinfo=None)
              , lambda secs: datetime.fromtimestamp(secs)
              )
        , Bank( 'Timezone Naive Datetime UTC'
              , lambda l,r: abs((r-l).total_seconds()) < 1
              , lambda dt: str(dt)
              , lambda: datetime.utcnow()
              , lambda dt: localtz.localize(dt).astimezone(pytz.utc).replace(tzinfo=None)
              , None
              , lambda dt: dt.astimezone(pytz.utc).replace(tzinfo=None)
              , lambda t: datetime.utcfromtimestamp(time.mktime(t))
              , lambda t: datetime.utcfromtimestamp(calendar.timegm(t))
              , lambda secs: datetime.utcfromtimestamp(secs)
              )
        , Bank( 'Timezone Aware Datetime'
              , lambda l,r: abs((r-l).total_seconds()) < 1
              , lambda dt: str(dt)
              , lambda : localtz.localize(datetime.now()).astimezone(othertz)
              , lambda dt: localtz.localize(dt).astimezone(othertz)
              , lambda dt: pytz.utc.localize(dt).astimezone(othertz)
              , None
              , lambda t: localtz.localize(datetime(*t[:6])).astimezone(othertz)
              , lambda t: pytz.utc.localize(datetime(*t[:6])).astimezone(othertz)
              , lambda secs: localtz.localize(datetime.fromtimestamp(secs))
              )
        , Bank( 'Time Struct Local'
              , lambda l,r: sum([abs(r[i]-l[i]) for i in range(6)]) == 0
              , lambda t: str(tuple(t))
              , lambda : time.localtime()
              , lambda dt: dt.timetuple()
              , lambda dt: pytz.utc.localize(dt).astimezone(localtz).timetuple()
              , lambda dt: dt.astimezone(localtz).timetuple()
              , None
              , lambda t: time.localtime(calendar.timegm(t))
              , lambda secs: time.localtime(secs)
              )
        , Bank( 'Time Struct UTC'
              , lambda l,r: sum([abs(r[i]-l[i]) for i in range(6)]) == 0
              , lambda t: str(tuple(t))
              , lambda : time.gmtime()
              , lambda dt: localtz.localize(dt).utctimetuple()
              , lambda dt: dt.utctimetuple()
              , lambda dt: dt.utctimetuple()
              , lambda t: time.gmtime(time.mktime(t))
              , None
              , lambda secs: time.gmtime(secs)
              )
        , Bank( 'Timestamp'
              , lambda l,r: abs(r-l) <= 1
              , lambda t: str(t)
              , lambda : time.time()
              , lambda dt: time.mktime(dt.timetuple())+1e-6*dt.microsecond
              , lambda dt: calendar.timegm(pytz.utc.localize(dt).timetuple())+1e-6*dt.microsecond
              , lambda dt: calendar.timegm(dt.utctimetuple())+1e-6*dt.microsecond
              , lambda t: time.mktime(t)
              , lambda t: calendar.timegm(t)
              , None
              )
        ]


def other():
    print '''

'''


def getLambdaSource(conversion, add_wbr=True):
    if conversion is None:
        return None
    code = conversion.func_code
    line = open(code.co_filename).readlines()[code.co_firstlineno-1]
    line = line[line.index(':')+1:].strip()

    unbreakables = [ '1e-6', '*t[:6]', ]

    if add_wbr:
        i = len(line)-1
        while i:
            for text in unbreakables:
                if text in line[i+1-len(text):i-1+len(text)]:
                    break
            else:
                if re.match(r'[A-Za-z0-9_][A-Za-z0-9_]', line[i-1:i+1]):
                    pass
                else:
                    line = line[:i] + ' ' + line[i:]
            i -= 1

    return line


def checkConversion(bank, conversion, from_bank, silent):
    if callable(conversion):
        line = getLambdaSource(conversion)
        result = conversion(from_bank.now)
        if not silent:
            print '{0} - {1}'.format(bank.str(result), line)
        match = bank.cmp_fn(bank.now,result)
        assert match, \
                ('Conversion result not close enough -'
                +' from {from_bank.name!r} to {bank.name!r}:'
                +'\nfrom  ={from_now}'
                +'\nresult={result}'
                +'\ntarget={to_now}'
                ).format( result=bank.str(result)
                        , bank=bank
                        , from_bank=from_bank
                        , from_now=from_bank.str(from_bank.now)
                        , to_now=bank.str(bank.now)
                        )


def checkConversions(args, silent=False):
    for index,bank in enumerate(Banks):
        assert len(bank.conversions) == len(Banks), \
                'Length of conversions mismatch for %s: had %d needs %d' % (
                        bank.name, len(bank.conversions), len(Banks) )
        assert bank.conversions[index] is None, \
                '{0.name!r} provided its own conversion.'.format(bank)

        if not silent:
            print '{bank.name!r} - {now}'.format( bank=bank
                                                , now=bank.str(bank.now))

        for cindex,conversion in enumerate(bank.conversions):
            from_bank = Banks[cindex]
            checkConversion(bank, conversion, from_bank, silent)


def n(elem, text=None, tail=None, subnodes = None, **kwargs):
    '''Helper function to generate an elementTree hierarchy for html.
       Examples:
            n('a', 'click here', '.' href='http://xyzzy.xyz/abc'
    '''

    # Create a new kwargs with string values.
    kwargs = dict( [ (k.lower(),str(v)) for k,v in kwargs.items() ] )

    if isinstance(elem, basestring):
        # As a shortcut, if the first item is a string we'll make it
        # an element and pass it the kwargs.
        elem = ET.Element(elem, ** ( dict( kwargs.items() ) ) )
    else:
        # If this isn't a string, it should be an Element and
        # any fields should be sent to it directly, not implicitly
        # as kwargs.
        assert len(kwargs) == 0, 'kwargs should be none for Elements: %r' % (
                                    kwargs, )

    if isinstance(text, list):
        # If text is a list, then these are actually subnodes, and
        # we have no text.
        assert subnodes is None
        subnodes = text
        text = None
    else:
        # If text is provided (and not a list as above), it must be a string.
        assert text is None or isinstance(text, basestring)

    if text is not None:
        elem.text = text
    if subnodes:
        for x in subnodes:
            elem.append(x)
    if tail is not None:
        elem.tail = tail
    return elem


def printHtml(args):
    checkConversions(args, silent=True)

    # Construct the table of conversions.
    rows = [ n('tr', [ n('td') ] +
                     [ n('th', 'To', subnodes=[n('br',bank.name)])
                       for bank in Banks ] )
           ]

    elems = [ n('th', 'Build as of now') ]
    for bank in Banks:
        elems.append( n('td', [n('span', getLambdaSource(bank.now_fn)
                                , CLASS='code' ) ]) )
    rows.append( n('tr', elems) )

    for index,from_bank in enumerate(Banks):
        elems = [ n('th', 'From', subnodes=[n('br',from_bank.name)]) ]
        for cindex,to_bank in enumerate(Banks):
            to_bank = Banks[cindex]
            conversion = to_bank.conversions[index]
            elems.append( n('td', [n( 'span', getLambdaSource(conversion) or
                                              ' '
                                    , CLASS="code") ] ) )
        rows.append( n('tr', elems) )

    table = n('table', rows, border="1")

    # Build the list of lists.
    convs = []
    for idx,bank in enumerate(Banks):
        convs.extend([ n('br')
                     , n('a', [n('br')], name=bank.name.replace(' ',''))
                     , n('h2', 'Converting to ', ''
                        ,[n('span', bank.name, CLASS='highlighted')])
                     , n( 'p', 'To build as of now: ', None
                        , [ n( 'span', getLambdaSource(bank.now_fn, False)
                             , CLASS="code"
                             ) ] )
                     ])
        tbl = [ n('tr', [ n('th', 'From'), n('th', 'To '+bank.name) ] ) ]
        tbl+= [ n('tr', [ n('td', Banks[i].name)
                        , n('td', [ n('span', getLambdaSource(conv, False)
                                     , CLASS='code') ]
                           )
                        ])
                for i,conv in enumerate(bank.conversions)
                if conv is not None
              ]
        convs.append( n('table', tbl, border="1") )

    print '''\
<html>
  <body>

<style type="text/css" scoped>
  .code { font-family:monospace; }
  .highlighted { color:red; background:yellow; }
</style>


<h2>Date Time, Timestamp and Datetime conversions</h2>

<P>
Python has a great class for storing and
manipulating the date and time: datetime.
</P>

<P>
Unfortunately, it is not the only way to refer to
a point in time. Sometimes you need to convert
between the two and I frequently forget how to do
it.
</P>


<h2>Table of Conversions</h2>
<P>
Here is a table of conversions. Pick the row
corresponding to the form of time that you have
(from the left), and them pick the column
corresponding to the form that you would like
(from the top). The intersecting cell is the code
snippet to get you there.
</P>

<P>
I have some measure of confidence in the correctness since
the table, indeed, this entire post, was created by a script
which tested the code shown in the table and lists below.
That script is available
<a href="https://github.com/marksantesson/web/blob/master/datetime.py">here</a>.
However, I expect that many of the conversions can be improved upon
and many may be subtly, or not so subtly, incorrect.
</P>

<ul>
<li>"dt" represents an input datetime.</li>
<li>"t" represents an input time struct.</li>
<li>"secs" represents an input timestamp (seconds since the Epoch GMT).</li>
<li>"localtz" represents the local timezone. This is necessary to account
    for functions or formats that convert to or from the local timezone.</li>
<li>"othertz" represents a timezone that you want to to have. It can be
    UTC or any other pytz timezone.</li>
<li>You need to import "pytz" for timezones.</li>
<li>You need to import the "datetime" class from the the datetime module.</li>
<li>Note that time structs can not store time at a resolution finer
    than a second.</li>
</ul>

<P>
I'm sorry, but this table just isn't going to work on mobile.
<a href="#conversionslist">Below</a> is
a breakout by the type of representation that you are converting to.
</P>


<a name="table" id="table"></a>
%(table)s

<a name="conversionslist" id="conversionslist"></a>
%(convs)s

<a name="timezones" id="timezones"><h2>Timezones</h2></a>
<p CLASS="code">
import pytz, datetime
<br>pytz.timezone('UTC').localize(datetime.utcnow())
<br>pytz.timezone('US/Central').localize(datetime.now())
<br>print 'Common timezones:',pytz.common_timezones
</p>


<h2>References</h2>

<ul>
<li><a href="http://www.seehuhn.de/pages/pdate">Even more formats.</a></li>
<li><a href="https://docs.python.org/2/library/time.html">Time module.</a></li>
<li><a href="https://docs.python.org/2/library/datetime.html">Datetime
    module.</a></li>
<li><a
    href="http://pytz.sourceforge.net/#localized-times-and-date-arithmetic">The
    pytz docs.</a> say to <a
    href="http://stackoverflow.com/a/12809533/4662">never
    create a datetime with a timezone that has DST.</a></li>
</ul>


  </body>
</html>
''' % dict( table=xml.dom.minidom.parseString(ET.tostring(table)).toprettyxml()
          , convs='\n'.join([ xml.dom.minidom.parseString(ET.tostring(x))
                              .toprettyxml() for x in convs ])
          )


if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Test datetime conversions')
    parser.add_argument( '--html', action='store_true'
                       , help='Output html page instead of testing results.' )
    args = parser.parse_args()

    if args.html:
        printHtml(args)
    else:
        checkConversions(args)

