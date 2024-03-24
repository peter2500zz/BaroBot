from action import *


def common_permission(sender: CheckPermission) -> bool:
    return sender.is_private_chat or sender.is_group_chat


@bot_command('ping', permission=common_permission)
def ping(session: Command) -> None:
    session.send('pong!')


@scheduled_job(every=1, freq='day', at='04:04')
def send_noise(session: Command) -> None:
    session.send_private(123123, 'hi')
