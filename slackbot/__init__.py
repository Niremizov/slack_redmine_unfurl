import os
import slack
import logging
import html2text

from flask import Flask
from slackeventsapi import SlackEventAdapter
from urllib.parse import urlparse
from redminelib import Redmine
from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.handlers.RotatingFileHandler',
        'formatter': 'default',
        'filename': 'logconfig.log',
        'maxBytes': 1024
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

redmine_key = os.environ["REDMINE_API_KEY"]
redmine_url = os.environ["REDMINE_URL"]
slack_signing_secret = os.environ["SLACK_SIGNING_SECRET"]
slack_bot_token = os.environ["SLACK_BOT_TOKEN"]

application = app = Flask(__name__)

redmine = Redmine(redmine_url, key=redmine_key)
slack_events_adapter = SlackEventAdapter(slack_signing_secret, "/slack/events", app)
slack_client = slack.WebClient(slack_bot_token)

def contents_issue(url, paths):
    try:
        issue = redmine.issue.get(paths[2])
    except Exception as e:
        print("Issue not found : " + paths[2])
        app.logger.debug("Issue not found : " + paths[2])
        app.logger.debug(str(e))
        return { "title" : "Omcode Redmine", "text" : "Задача не найдена." }

    user = redmine.user.get(issue.assigned_to.id)
    author = redmine.user.get(issue.author.id)

    h = html2text.HTML2Text()
    h.ignore_links = True
    description = h.handle(issue.description)

    if "created_on" in dir(issue):
        create_date = " " + issue.created_on.strftime("%Y/%m/%d") + " "
    else:
        create_date = ""

    if "due_date" in dir(issue):
        due_date = issue.due_date.strftime("%Y/%m/%d")
    else:
        due_date = "due"

    content = {
            "title" : issue.project.name + " #" + paths[2] + " " + issue.subject,
            "title_link" : url,
            "color" : "#7cd197",
            #"author_name" : issue.author.name + "(<@" + author.login + ">)" + create_date,
            #"fields" : [
                #{ "title" : "Назначено на:", "value" : issue.assigned_to.name + " <@" + user.login + ">", "short" : False },
                #{ "title" : "Статус:", "value" : issue.status.name, "short" : True },
                #{ "title" : "Приоритет:", "value" : issue.priority.name, "short" : True },
                #{ "title" : "С:", "value" : issue.start_date.strftime("%Y/%m/%d"), "short" : True},
                #{ "title" : "До:", "value" : due_date, "short" : True }
            #],
            #"text" : description,
            "footer" : "Omcode"
    }
    return content

def contents_version(url, paths):
    try:
        version = redmine.version.get(paths[2])
    except Exception as e:
        print("Version not found : " + paths[2])
        app.logger.debug("Version not found : " + paths[2])
        app.logger.debug(str(e))
        return { "title" : "Omcode Redmine", "text" : "Версия не найдена." }

    h = html2text.HTML2Text()
    h.ignore_links = True
    description = h.handle(version.description)

    content = {
            "title" : version.project.name + " @" + version.name,
            "title_link" : url,
            "color" : "#7c97d1",
            "text" : description,
            "fields" : [
                { "title" : "test", "value" : version.status, "short" : True },
                { "title" : "Срок", "value" : version.due_date.strftime("%Y/%m/%d") if hasattr(version, "due_date") else "Не установлен", "short" : True }
            ]
    }

    return content

def parse_url(url):
    parsed = urlparse(url)

    paths = parsed.path.split('/')

#    if parsed.netloc == redmine_url and paths[1] == "issues":
    if paths[1] == "issues":
        return contents_issue(url, paths)
    elif paths[1] == "versions":
        return contents_version(url, paths)
    else:
        return ""

@slack_events_adapter.on("link_shared")
def handle_unfurl(event_data):
    app.logger.debug('Unfurl attempt.')
    message = event_data["event"]
    channel = message["channel"]
    message_ts = message["message_ts"]

    unfurls = {}

    app.logger.debug("before unfurl")

    try:
        for link in message["links"]:
            url = link["url"]
            unfurls[url] = parse_url(url)

        app.logger.debug("before send")
        result = slack_client.api_call(api_method="chat.unfurl", json={'ts':message_ts, 'channel': channel, 'unfurls':unfurls})
    except Exception as e:
        app.logger.error(str(e))

    app.logger.debug(str(result))
    app.logger.debug("response sended")
    if result["ok"] != True:
        print(result["error"])
        app.logger.error(result["error"])

@slack_events_adapter.on("error")
def error_handler(err):
    app.logger.error("ERROR: " + str(err))
    print("ERROR: " + str(err))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3001)
