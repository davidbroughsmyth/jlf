"""
Jira Stats Publisher.

Takes a report config detailing which reports to publish and
a Jira Wrapper which provides the data for the reports
"""

import os
import pandas as pd

from xlsxwriter.utility import xl_rowcol_to_cell

_state_default_colours = ['#8dd3c7',
                          '#ffffb3',
                          '#bebada',
                          '#fb8072',
                          '#80b1d3',
                          '#fdb462',
                          '#b3de69',
                          '#fccde5',
                          '#d9d9d9',
                          '#bc80bd',
                          '#ccebc5',
                          '#ffed6f']

def publish(config, jira, from_date, to_date):
    
    writer = None

    if config['format'] == 'xlsx':
        excel_basename = config['name']
        excel_filename = os.path.join(config['location'], 
                                      excel_basename + '.xlsx')
        writer = pd.ExcelWriter(excel_filename, engine='xlsxwriter')


    for report in config['reports']:

        data = None

        types = None

        try:
            types = report['types']
            if types == 'foreach':
                types = []
                for type in config['types']:
                    types.append(type)
        except KeyError:
            # Not all reports require types
            pass

        if report['metric'] == 'throughput':

            data = jira.throughput(from_date,
                                   to_date,
                                   cumulative=False,
                                   types=types)

        if report['metric'] == 'cumulative-throughput':
            data = jira.throughput(from_date, to_date, cumulative=True, types=types)

        if report['metric'] == 'cfd':
            data = jira.cfd(from_date, to_date)

        if report['metric'] == 'demand':
            data = jira.demand(from_date, to_date, report['types'])

        if report['metric'] == 'detail':
            # It seems inconsistent that 'done' does not allow you to specify a date range.
            # If it did then all the metric functions could have the same interface
            # so making this code DRYer and more succinct
            if 'fields' in report:
                fields = report['fields']
            else:
                fields = None
            data = jira.issues(fields=fields)

        if report['metric'] == 'cycle-time':
            types = None
            if 'types' in report:
                types = report['types']

            buckets = None
            if 'buckets' in report:
                buckets = report['buckets']
            data = jira.cycle_time_histogram(report['cycles'][0], types=types, buckets=buckets)

        if report['metric'] == 'arrival-rate':
            data = jira.arrival_rate(from_date, to_date)

        if report['metric'] == 'history':
            data = jira.history(from_date, to_date)

        if data is not None:
            if isinstance(writer, pd.ExcelWriter):

                sheet_name = []
                try:
                    if isinstance(report['types'], list):
                        sheet_name.extend(report['types'])

                    if isinstance(report['cycles'], list):
                        sheet_name.extend(report['cycles'])

                except KeyError:
                    pass

                sheet_name.append(report['metric'])

                data.to_excel(writer, worksheet_title('-'.join(sheet_name)))

                if report['metric'] == 'cfd':
                    if 'format' in report:
                        formats = report['format']
                    else:
                        formats = format_states(config['states'])
                    workbook = writer.book
                    sheets = [sheet for sheet in workbook.worksheets() if sheet.name == 'cfd']
                    # Do the colouring in

                    colour_cfd(workbook, sheets[0], data, formats)

                ### WARNING CUT AND PASTE ALERT!

                if report['metric'] == 'history':
                    if 'format' in report:
                        formats = report['format']
                    else:
                        formats = format_states(config['states'])
                    workbook = writer.book
                    sheets = [sheet for sheet in workbook.worksheets() if sheet.name == 'history']
                    # Do the colouring in

                    colour_cfd(workbook, sheets[0], data, formats)


    if isinstance(writer, pd.ExcelWriter):
        writer.save()

def format_states(states):

    formats = {}
    
    for index, state in enumerate(states):
        try:
            formats[state] = {'color': _state_default_colours[index]}
        except IndexError:
            rebased_index = index
            while rebased_index >= len(_state_default_colours):
                rebased_index = rebased_index - len(_state_default_colours)
            formats[state] = {'color': _state_default_colours[rebased_index]}

    return formats

def colour_cfd(workbook, worksheet, data, formats):

    workbook_formats = {}

    for i, row in enumerate(data.values):
        for j, cell in enumerate(row):

            try:
                color = formats[cell]['color']
                if color not in workbook_formats:

                    new_format = workbook.add_format()
                    new_format.set_bg_color(color)
                    workbook_formats[color] = new_format

                cell_ref = xl_rowcol_to_cell(i+1, j+1)
                worksheet.write(cell_ref, cell, workbook_formats[color])
            except KeyError:
                pass

def worksheet_title(full_title):
    """
    Shorten the title if it is not going to fit on the worksheet
    """

    _MAX_LENGTH = 30

    excess = len(full_title) - _MAX_LENGTH

    if excess > 0:
        parts = full_title.split('-')
        shorten_by = excess / len(parts)

        short_title = full_title

        while len(short_title) > _MAX_LENGTH:
            longest = max(parts[:-1], key=len)
            if len(longest) > shorten_by:
                parts[parts.index(longest)] = longest[:-shorten_by]

                short_title = ''
                for part in parts[:-1]:
                    short_title += part
                    short_title += '-'

                short_title += parts[-1]
            else:
                short_title = short_title[:_MAX_LENGTH-len(parts[-1])] + parts[-1]

        return short_title

    else:
        return full_title