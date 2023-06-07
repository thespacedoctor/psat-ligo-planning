#!/usr/bin/env python
# encoding: utf-8
"""
*This gocart plugin will parse alert metadata and ingest it into a mysql database table (called `alerts`). It will also create an `events` view with the latest summary info for each event*

You need to add your database settings to the gocart.yaml file in this format:

```yaml
database settings:
    db: lvk
    host: localhost
    user: myuser
    password: mypass
```

You will also need this installs:

```bash
conda install unicodecsv pymysql -c conda-forge
```

:Author:
    David Young

:Date Created:
    May 11, 2023

Usage:
    gp_alerts_to_db <alertDir>

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
        dbConn):
    """*this is the gocart plugin function that will be run when an alert is read*

    **Key Arguments:**

    - ``log`` -- logger
    - ``settings`` -- these are the gocart settings, you can add extra settings to the gocart.yaml settings file and they will be read here.
    - ``alertFiles`` -- a list of all the files generated by gocart for the alert
    - ``alertMeta`` -- a dictionary of the alert metadata from the json alert, FITS Heaeder and gocart generated extras. 
    - ``dbConn`` -- the database connection     
    """
    log.debug('starting the ``plugin`` function')

    # BUNDLE THE ALERT DATA TOGETHER
    alertDict = {}

    for k, v in alertMeta["ALERT"].items():
        if not isinstance(v, dict):
            alertDict[k.lower()] = v
    if "event" in alertMeta["ALERT"] and alertMeta["ALERT"]["event"]:
        for k, v in alertMeta["ALERT"]["event"].items():
            if not isinstance(v, dict) and not isinstance(v, list):
                alertDict[k.lower()] = v
        if "classification" in alertMeta["ALERT"]["event"] and alertMeta["ALERT"]["event"]["classification"]:
            for k, v in alertMeta["ALERT"]["event"]["classification"].items():
                if not isinstance(v, dict):
                    alertDict[f"class_{k}".lower()] = v
        if "properties" in alertMeta["ALERT"]["event"] and alertMeta["ALERT"]["event"]["properties"]:
            for k, v in alertMeta["ALERT"]["event"]["properties"].items():
                if not isinstance(v, dict):
                    alertDict[f"prop_{k}".lower()] = v
    if "EXTRA" in alertMeta and alertMeta["EXTRA"]:
        for k, v in alertMeta["EXTRA"].items():
            if not isinstance(v, dict):
                alertDict[k.lower()] = v
        alertDict["ra_centre"] = alertMeta["EXTRA"]['central coordinate']["equatorial"].split()[0]
        alertDict["dec_centre"] = alertMeta["EXTRA"]['central coordinate']["equatorial"].split()[1]

    if "HEADER" in alertMeta and alertMeta["HEADER"]:
        allowList = ["CREATOR", "DATE-OBS", "DISTMEAN", "DISTSTD", "LOGBCI", "LOGBSN", "MJD-OBS"]
        for k, v in alertMeta["HEADER"].items():
            if not isinstance(v, dict) and k in allowList:
                alertDict[k.lower()] = v
    # CLEANING
    if "far" in alertDict:
        alertDict["far_hz"] = alertDict.pop("far")
        far_years = 1 / (float(alertDict["far_hz"]) * 60. * 60. * 24.)
        alertDict["far_years"] = float(f"{far_years:0.2f}")
    if "time_created" in alertDict:
        alertDict["alert_time"] = alertDict.pop("time_created")
        if "time" in alertDict:
            from datetime import datetime
            try:
                delta = datetime.strptime(alertDict["alert_time"], '%Y-%m-%dT%H:%M:%SZ') - datetime.strptime(alertDict["time"], '%Y-%m-%dT%H:%M:%S.%fZ')
                alertDict["alert_delta_sec"] = int(delta.seconds)
            except:
                pass
            alertDict.pop("time")

    if 'significant' in alertDict:
        if alertDict['significant']:
            alertDict['significant'] = 1
        else:
            alertDict['significant'] = 0

    for f in alertFiles:
        if os.path.splitext(f)[1] == ".fits":
            alertDict["map"] = f

    sqlQuery = f"""CREATE TABLE IF NOT EXISTS `alerts` (
      `superevent_id` varchar(20) NOT NULL,
      `significant` tinyint(4)  DEFAULT NULL,
      `alert_type` varchar(20) DEFAULT NULL,
      `alert_time` datetime DEFAULT NULL,
      `alert_delta_sec` int(11) DEFAULT NULL,
      `date_obs` datetime DEFAULT NULL COMMENT 'original keyword: date-obs',
      `mjd_obs` double DEFAULT NULL COMMENT 'original keyword: mjd-obs',
      `far_hz` double DEFAULT NULL,
      `far_years` double DEFAULT NULL,
      `distmean` double DEFAULT NULL,
      `diststd` double DEFAULT NULL,
      `class_bbh` double DEFAULT NULL,
      `class_bns` double DEFAULT NULL,
      `class_nsbh` double DEFAULT NULL,
      `class_terrestrial` double DEFAULT NULL,
      `prop_hasns` double DEFAULT NULL,
      `prop_hasremnant` double DEFAULT NULL,
      `prop_hasmassgap` double DEFAULT NULL,
      `area10` double DEFAULT NULL,
      `area50` double DEFAULT NULL,
      `area90` double DEFAULT NULL,
      `creator` varchar(30) DEFAULT NULL,
      `ra_centre` double DEFAULT NULL,
      `dec_centre` double DEFAULT NULL,
      `group` varchar(100) DEFAULT NULL,
      `logbci` double DEFAULT NULL,
      `logbsn` double DEFAULT NULL,
      `pipeline` varchar(100) DEFAULT NULL,
      `search` varchar(100) DEFAULT NULL,
      `map` varchar(400) DEFAULT NULL,
      `dateAdded` datetime DEFAULT current_timestamp(),
      `dateLastModified` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
      UNIQUE KEY `superevent_id_alert_time_alert_type` (`superevent_id`,`alert_time`, `alert_type`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
    """
    writequery(
        log=log,
        sqlQuery=sqlQuery,
        dbConn=dbConn,
    )

    sqlQuery = f"""CREATE OR REPLACE VIEW `events` AS
    (SELECT 
        a.superevent_id,
        b.significant,
        a.alert_type AS latest_alert,
        a.alert_time,
        a.alert_delta_sec,
        b.date_obs,
        b.mjd_obs,
        b.far_hz,
        b.far_years,
        b.distmean,
        b.diststd,
        b.class_bbh,
        b.class_bns,
        b.class_nsbh,
        b.class_terrestrial,
        b.prop_hasns,
        b.prop_hasremnant,
        b.prop_hasmassgap,
        b.area10,
        b.area50,
        b.area90
    FROM
        (SELECT 
            alerts.*
        FROM
            alerts, (SELECT 
            superevent_id, MAX(alert_time) AS alert_time
        FROM
            alerts
        GROUP BY superevent_id) latest_alert
        WHERE
            alerts.superevent_id = latest_alert.superevent_id
                AND alerts.alert_time = latest_alert.alert_time) a,
        (SELECT 
            alerts.*
        FROM
            alerts, (SELECT 
            superevent_id, MAX(alert_time) AS alert_time
        FROM
            alerts
        WHERE
            alert_type != 'RETRACTION'
        GROUP BY superevent_id) latest_alert
        WHERE
            alerts.superevent_id = latest_alert.superevent_id
                AND alerts.alert_time = latest_alert.alert_time) b
    WHERE
        a.superevent_id = b.superevent_id);
    """
    writequery(
        log=log,
        sqlQuery=sqlQuery,
        dbConn=dbConn,
    )

    from fundamentals.mysql import insert_list_of_dictionaries_into_database_tables
    # USE dbSettings TO ACTIVATE MULTIPROCESSING - INSERT LIST OF DICTIONARIES INTO DATABASE
    insert_list_of_dictionaries_into_database_tables(
        dbConn=dbConn,
        log=log,
        dictList=[alertDict],
        dbTableName="alerts",
        dateModified=False,
        dateCreated=False,
        batchSize=2500,
        replace=True,
    )

    export_alerts_table_to_csv(log=log, dbConn=dbConn, settings=settings)

    log.debug('completed the ``plugin`` function')
    return None


def export_alerts_table_to_csv(
        log,
        dbConn,
        settings):
    """*export the alerts table and events view to CSV files*

        **Key Arguments:**

        - `dbConn` -- mysql database connection
        - `log` -- logger

        **Usage:**

        ```eval_rst
        .. todo::

                add usage info
                create a sublime snippet for usage
        ```

        ```python
        usage code 
        ```           
        """
    log.debug('starting the ``export_alerts_table_to_csv`` function')

    now = datetime.now()
    now = now.strftime("%Y-%m-%d %H:%M:%S")

    for ttype in ['parse_mock_events', 'parse_real_events']:
        if not settings['lvk'][ttype]:
            continue
        else:
            pass

        if 'mock' in ttype:
            ddir = "mockevents"
            prefix = "M"
        else:
            ddir = "superevents"
            prefix = "S"

        for sig in ['all', False, True]:

            if sig == 'all':
                sigDir = ""
                sigSql = ""
            elif sig:
                sigDir = "/_high_significance"
                sigSql = " and significant = 1"
            elif not sig:
                sigDir = "/_low_significance"
                sigSql = " and significant = 0"

            exists = os.path.exists(settings['lvk']['download_dir'] + f"/{ddir}{sigDir}")
            if not exists:
                continue

            alertCsvPath = settings['lvk']['download_dir'] + f"/{ddir}{sigDir}/alerts.csv"
            eventsCsvPath = settings['lvk']['download_dir'] + f"/{ddir}{sigDir}/events.csv"

            # EVENTS VIEW EXPORT
            sqlQuery = f"""
                select * from events where superevent_id like "{prefix}%" {sigSql};
            """
            rows = readquery(
                log=log,
                sqlQuery=sqlQuery,
                dbConn=dbConn,
                quiet=False
            )
            dataSet = list_of_dictionaries(
                log=log,
                listOfDictionaries=rows
            )
            csvData = dataSet.csv(filepath=None)
            tableData = dataSet.table(filepath=None)
            csvData = f"# Exported {now}\n" + csvData
            tableData = f"# Exported {now}\n" + tableData
            myFile = open(eventsCsvPath, 'w')
            myFile.write(csvData)
            myFile.close()
            myFile = open(eventsCsvPath.replace(".csv", ".txt"), 'w')
            myFile.write(tableData)
            myFile.close()

            # ALERTS TABLE EXPORT
            sqlQuery = f"""
                select * from alerts where superevent_id like "{prefix}%" order by alert_time desc;
            """
            rows = readquery(
                log=log,
                sqlQuery=sqlQuery,
                dbConn=dbConn,
                quiet=False
            )
            dataSet = list_of_dictionaries(
                log=log,
                listOfDictionaries=rows
            )
            csvData = dataSet.csv(filepath=None)
            tableData = dataSet.table(filepath=None)
            csvData = f"# Exported {now}\n" + csvData
            tableData = f"# Exported {now}\n" + tableData
            myFile = open(alertCsvPath, 'w')
            myFile.write(csvData)
            myFile.close()
            myFile = open(alertCsvPath.replace(".csv", ".txt"), 'w')
            myFile.write(tableData)
            myFile.close()

    log.debug('completed the ``export_alerts_table_to_csv`` function')
    return None

# use the tab-trigger below for new function
# xt-def-function


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
        dbConn=dbConn
    )

    return


if __name__ == '__main__':
    main()
