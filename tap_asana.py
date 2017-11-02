import argparse
import requests
import singer
import json
import os
import asana
import datetime
import singer.metrics as metrics

# cceb1f549c2048d6093c9af891470ad1ffa3f55e88073a1ad2051cde510df09e

logger = singer.get_logger()

def get_abs_path(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)

def load_schemas():
    schemas = {}

    with open(get_abs_path('tap_asana/schemas/tasks.json')) as file:
        schemas['tasks'] = json.load(file)

    with open(get_abs_path('tap_asana/schemas/stories.json')) as file:
        schemas['stories'] = json.load(file)

    return schemas

def get_all_tasks(config, state):
    if 'tasks' in state and state['tasks'] is not None:
        since = format(state['tasks'])
    else:
        since = ''

    client = asana.Client.access_token(config['access_token'])
    latest_modified_time = None

    with metrics.record_counter('tasks') as counter:
        
        for project_id in config['projects']:

            tasks = client.tasks.find_all({'project': project_id})
            tasks_output = []
            stories_output = []

            for task in tasks:
                counter.increment()
                task = client.tasks.find_by_id(task['id'])
                task.pop('enum_options', None)
                task.pop('custom_fields', None)
                task.pop('hearts', None)
                tasks_output.append(task)

                stories = client.stories.find_by_task(task['id'])

                for story in stories:
                    story['task_id'] = task['id']
                    stories_output.append(story)

            tasks_output
            singer.write_records('tasks', tasks_output)
            singer.write_records('stories', stories_output)

    state['tasks'] = str(datetime.datetime.now())
    return state

def do_sync(config, state):
    schemas = load_schemas()

    if state:
        logger.info('Replicating tasks since %s', state)
    else:
        logger.info('Replicating all tasks')

    singer.write_schema('tasks', schemas['tasks'], 'id')
    singer.write_schema('stories', schemas['stories'], 'id')
    state = get_all_tasks(config, state)
    singer.write_state(state)

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-c', '--config', help='Config file', required=True)
    parser.add_argument(
        '-s', '--state', help='State file')

    args = parser.parse_args()

    with open(args.config) as config_file:
        config = json.load(config_file)

    missing_keys = []
    for key in ['access_token', 'projects']:
        if key not in config:
            missing_keys += [key]

    if len(missing_keys) > 0:
        logger.fatal("Missing required configuration keys: {}".format(missing_keys))
        exit(1)

    state = {}
    if args.state:
        with open(args.state, 'r') as file:
            for line in file:
                state = json.loads(line.strip())

    do_sync(config, state)

if __name__ == '__main__':
    main()