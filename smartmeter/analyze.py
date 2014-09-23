import datetime
from fnmatch import fnmatch
import logging
import os

import numpy as np
import pandas as pd

SEP_LINE = '='*33

pd.set_option('display.precision', 4)

log = logging.getLogger(__name__)


class InputError(Exception):
    """Raised if there was a problem with input files."""
    def __init__(self, msg, input=None):
        self.msg = msg
        self.input = input

    def __str__(self):
        if self.input:
            return "{msg}: {input}".format(msg=self.msg, input=self.input)
        else:
            return str(self.msg)


class FileDataSource(object):
    """A collection of csv files which are used as data source."""

    def __init__(self, sources=[], pattern='*.csv'):
        self.sources = []
        self.raw_sources = {}
        self.cached_data = None
        for source in sources:
            self.add_source_directory(source, pattern)

    def add_source_file(self, file):
        if not os.path.isfile(file):
            raise InputError('CSV file not found', input=file)
        self.raw_sources[file] = None
        self.sources += [file]
        return file

    def add_source_directory(self, directory, pattern):
        if os.path.isdir(directory):
            self.raw_sources[directory] = pattern
            sources = self._find_files(directory, pattern)
            self.sources += sources
            return sources
        else:
            return self.add_source_file(directory)

    def _find_files(self, directory, pattern):
        filelist = []
        for root, dirs, files in os.walk(directory, followlinks=True):
            filelist += [os.path.join(root, f)
                         for f in files if fnmatch(f, pattern)]
        return filelist

    def refresh_sources(self):
        sources = []
        for dir, pattern in self.raw_sources:
            if pattern:
                sources += self._find_files(dir, pattern)
            else:
                sources += [dir]
        log.info("{} files found. (previously: {})".format(len(sources),
                                                           len(self.sources)))
        self.sources = sources

    def read_data(self):
        self.cached_data = _read_consumption_csv(self.sources)
        return self.cached_data

    def get_data(self):
        if self.cached_data:
            return self.cached_data
        else:
            return self.read_data()

    def drop_cache(self):
        self.cached_data = None


def _read_consumption_csv(filenames):
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


def print_comparisons(data, due_date=None):
    # build cumulative sums:
    data['month'] = data.index.month
    group = data.groupby('month')
    data['cumulative_usage'] = group['usage'].cumsum()
    # compare with previous cumulative sum of previous group (month/year):
    if due_date is None:
        due_date = data.index.max().date()
    current_usage = data.loc[due_date, 'cumulative_usage']
    previous_date = _previous_month(due_date)
    previous_usage = data.loc[previous_date, 'cumulative_usage']
    previous_end_date = _previous_month_end(due_date)
    previous_monthly_usage = data.loc[previous_end_date, 'cumulative_usage']
    cumulative_delta = current_usage - previous_usage
    print "MONTHLY COMPARISONS:"
    print SEP_LINE
    print "Last month:    {} kWh\t({})".format(previous_monthly_usage,
                                               previous_end_date)
    print "Current month: {} kWh\t({})".format(current_usage, due_date)
    print "Difference:    {0:+} kWh\t({1})".format(cumulative_delta,
                                                   previous_date)


def _previous_month(date):
    prev_month = date
    while prev_month.month == date.month or date.day < prev_month.day:
        prev_month -= datetime.timedelta(days=1)
    return prev_month


def _previous_month_end(date):
    return date.replace(day=1) - datetime.timedelta(days=1)
