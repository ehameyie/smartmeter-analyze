import os
from fnmatch import fnmatch
import logging

import pandas as pd
import numpy as np

SEP_LINE = '='*33

pd.set_option('display.precision', 4)

log = logging.getLogger(__name__)


class InputError(Exception):

    def __init__(self, msg, input=None):
        self.msg = msg
        self.input = input

    def __str__(self):
        if self.input:
            return "{msg}: {input}".format(msg=self.msg, input=self.input)
        else:
            return str(self.msg)


def _get_filelist_from_dir(dir, pattern):
    filelist = []
    for root, dirs, files in os.walk(dir, followlinks=True):
        filelist += [os.path.join(root, f)
                     for f in files if fnmatch(f, pattern)]
    return filelist


def _prepare_filelist(arg, pattern):
    filenames = []
    for path in arg:
        if os.path.isdir(path):
            filenames += _get_filelist_from_dir(path, pattern)
        elif os.path.isfile(path):
            filenames += [path]
        else:
            raise InputError('CSV files not found', input=path)
    return filenames


def read_consumption_csv(filenames, pattern):
    filenames = _prepare_filelist(filenames, pattern)
    log.debug('Reading files: ' + repr(filenames))
    if not filenames:
        raise InputError('CSV files not found.')
    usages = []
    for filename in filenames:
        usages += [pd.read_csv(filename,
                               delimiter=';',
                               header=0,  # ignore header
                               usecols=[0, 1],  # third column is empty
                               names=['date', 'usage'],
                               index_col='date',  # use date as index
                               decimal=',',
                               parse_dates=True,
                               infer_datetime_format=True,
                               dayfirst=True,  # csv dateformat: DD.MM.YYYY
                               )]

    usage_union = pd.concat(usages)
    usage_union.sort_index(inplace=True)
    usage_unique = usage_union.groupby(usage_union.index).first()
    log.info('read_consumption_csv: IN={} OUT={}'.format(len(usage_union),
                                                         len(usage_unique)))
    return usage_unique


def print_summary(data):
    """Print summary of the given DataFrame.
    The summary includes the date range, nonthly and daily averages and the days
    with the minimum and maximum usage/consumption.

    Arguments:
    data -- pandas.DataFrame containing at least a date and a usage column.
    """
    data['month'] = data.index.month
    month_group = data.groupby('month')
    aggregates = [[data.usage.sum()],
                  [month_group[['usage']].sum()[:-1].usage.mean()],
                  [data.usage.mean()],
                  ]
    extrema = [[data.usage.idxmin(), data.usage.min()],
               [data.usage.idxmax(), data.usage.max()],
               ]
    print "CONSUMPTION SUMMARIES"
    print SEP_LINE
    print "from {}".format(data.index.min().date())
    print "to   {}".format(data.index.max().date())
    print "({} days)".format(data.usage.count())
    print SEP_LINE
    print pd.DataFrame(aggregates,
                       columns=['usage [kWh]'],
                       index=['sum', 'monthly average', 'daily average'])
    print SEP_LINE
    print pd.DataFrame(extrema,
                       columns=['date', 'usage [kWh]'],
                       index=['min', 'max'])


def print_stats_week(data):
    weekdays = ['Monday',
                'Tuesday',
                'Wednesday',
                'Thursday',
                'Friday',
                'Saturday',
                'Sunday']
    data['weekday'] = data.index.weekday
    weekday_group = data.groupby('weekday')
    weekday_avg = weekday_group.aggregate(np.mean)
    weekday_avg.index = weekdays
    weekday_avg.index.name = 'Weekday'
    weekly_avg = weekday_avg.sum()

    print "WEEK STATS:"
    print SEP_LINE
    print weekday_avg[['usage']]
    print "\nweekly average:   {} kWh".format(round(weekly_avg, 3))
