from action import *


def common_permission(sender: CheckPermission) -> bool:
    return sender.is_private_chat or sender.is_group_chat


@bot_command('pong', permission=common_permission)
def pong(session: Command) -> None:
    group_data = session.action('get_group_info', {'group_id': 631449318})
    session.send(str(group_data))
