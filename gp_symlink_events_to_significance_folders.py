#!/usr/bin/env python
# encoding: utf-8
"""
*This gocart plugin will create low and high-significance folders and symlink the events into them*

:Author:
    David Young

:Date Created:
    June 6, 2023

Usage:
    gp_symlink_events_to_significance_folders.py <alertDir>

Options:
    alertDir              path to an alert directory

    -h, --help            show this help message
    -v, --version         show version
"""
################# GLOBAL IMPORTS ####################
import sys
import os
from fundamentals import tools
from fundamentals.mysql import writequery
from fundamentals.mysql import readquery
from fundamentals.renderer import list_of_dictionaries
from datetime import datetime, date, time


def plugin(
        log,
        settings,
        alertFiles,
        alertMeta,
        dbConn,
        alertDir):
    """*this is the gocart plugin function that will be run when an alert is read*

    **Key Arguments:**

    - ``log`` -- logger
    - ``settings`` -- these are the gocart settings, you can add extra settings to the gocart.yaml settings file and they will be read here.
    - ``alertFiles`` -- a list of all the files generated by gocart for the alert
    - ``alertMeta`` -- a dictionary of the alert metadata from the json alert, FITS Heaeder and gocart generated extras. 
    - ``dbConn`` -- the database connection   
    - ``alertDir`` -- path to the alert directory  
    """
    log.debug('starting the ``plugin`` function')

    if alertDir[-1] == "/":
        alertDir = alertDir[:-1]

    eventDir = os.path.dirname(alertDir)
    basename = os.path.basename(eventDir)
    parentDir = os.path.dirname(eventDir)
    # Recursively create missing directories
    ls = parentDir + "/_low_significance"
    hs = parentDir + "/_high_significance"
    if not os.path.exists(ls):
        os.makedirs(ls)
    if not os.path.exists(hs):
        os.makedirs(hs)

    # IS THE EVENT SIGNIFICANT?
    if 'event' in alertMeta['ALERT'] and alertMeta['ALERT']['event']:
        if "significant" in alertMeta['ALERT']['event']:
            if alertMeta['ALERT']['event']["significant"]:
                dest = hs + "/" + basename
            else:
                dest = ls + "/" + basename

            print(eventDir, dest)
            if not os.path.exists(dest):
                os.symlink(eventDir, dest)

    log.debug('completed the ``plugin`` function')
    return None


# DO NOT EDIT ANYTHING BOTH THIS LINE
def main(arguments=None):
    """
    *The main function used when ``gp_template.py`` is run as a single script from the cl*
    """

    # SETUP THE COMMAND-LINE UTIL SETTINGS
    su = tools(
        arguments=arguments,
        docString=__doc__,
        logLevel="WARNING",
        options_first=False,
        projectName="gocart",
        defaultSettingsFile=True
    )
    arguments, settings, log, dbConn = su.setup()

    # UNPACK REMAINING CL ARGUMENTS USING `EXEC` TO SETUP THE VARIABLE NAMES
    # AUTOMATICALLY
    a = {}
    for arg, val in list(arguments.items()):
        if arg[0] == "-":
            varname = arg.replace("-", "") + "Flag"
        else:
            varname = arg.replace("<", "").replace(">", "")
        a[varname] = val
        if arg == "--dbConn":
            dbConn = val
            a["dbConn"] = val
        log.debug('%s = %s' % (varname, val,))

    # GENERATE A LIST OF FILE PATHS
    pathToDirectory = a["alertDir"]
    alertFiles = []
    alertMeta = None
    for d in os.listdir(pathToDirectory):
        filepath = os.path.join(pathToDirectory, d)
        if os.path.isfile(filepath) and d[0] != ".":
            alertFiles.append(filepath)

        if d == "meta.yaml":
            import yaml
            # ADD YAML CONTENT TO DICTIONARY
            with open(filepath, 'r') as stream:
                alertMeta = yaml.safe_load(stream)

    plugin(
        log=log,
        settings=settings,
        alertFiles=alertFiles,
        alertMeta=alertMeta,
        dbConn=dbConn,
        alertDir=pathToDirectory
    )

    return


if __name__ == '__main__':
    main()
