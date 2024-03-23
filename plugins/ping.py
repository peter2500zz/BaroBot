from action import *


@bot_command('/pong')
def pong(session: Command) -> None:
    group_data = session.action('get_group_info', {'group_id': 631449318})
    session.send(str(group_data))
