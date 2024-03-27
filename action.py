import websocket
from collections import defaultdict
import queue
import threading
import uuid
import json
from typing import Callable

# echo返回等待事件队列
echo_events = defaultdict(
    lambda: {"event": threading.Event(), "queue": queue.Queue()})


class CheckPermission:
    def __init__(self, data: dict):
        self.is_private_chat: bool = data.get('message_type') == 'private'
        self.is_group_chat: bool = data.get('message_type') == 'group'
        self.user_id: int = data.get('user_id')
        self.group_id: int | None = data.get('group_id')


class Command:
    def __init__(self, ws: websocket.WebSocket, data: dict = None):
        self.data = data
        self.ws = ws

    # 发送请求 在非多线程执行时要 小 心 阻 塞
    def action(self, action: str, params: dict = None, *, echo_needed: bool = True,
               timeout=5) -> None | dict:
        """
        向shamrock发送制定接口的请求

        :param action: 将要请求的接口
        :param params: 接口的参数
        :param echo_needed: 是否需要等待响应
        :param timeout: 等待响应的秒数
        :return: 当接收到响应时返回响应（字典） 无响应时返回None
        """

        ws = self.ws

        if echo_needed:
            echo = str(uuid.uuid4())
        else:
            echo = None

        if params is None:
            params = {}

        data = {
            "action": action,
            "params": params,
            "echo": echo
        }

        ws.send(json.dumps(data))

        response = None

        if echo:
            # 等待特定echo的消息返回
            event = echo_events[echo]["event"]
            # 这里使用 wait 方法的超时功能
            event_occurred = event.wait(timeout)  # 等待事件，带有超时

            if event_occurred:
                # 获取响应数据
                response = echo_events[echo]["queue"].get()
            else:
                # 超时处理
                print(f"超时：未能在 {timeout} 秒内收到响应")

            # 无论是否超时，都需要清理
            event.clear()  # 重置事件
            del echo_events[echo]

        return response

    def send(self, message: str | dict | list, auto_escape: bool = False,
             recall_duration: int = None, *, echo_needed: bool = False, timeout=5) -> None | dict:
        """
        发送消息 发送到与接收的消息相同的环境中

        :param message: 消息内容，可以是CQ码或是消息段/消息段组合 文档：https://whitechi73.github.io/OpenShamrock/message/format.html#%E7%BB%84%E5%90%88
        :param auto_escape: 是否解析CQ码（True为不解析）
        :param recall_duration: 自动撤回时间间隔（毫秒）
        :param echo_needed: 是否需要等待响应 默认不等待
        :param timeout: 等待响应的秒数
        :return: 当接收到响应时返回响应（message_id: int 消息 ID, time: int64 时间戳） 无响应时返回None
        """

        if self.data is None:
            print('在未给予data的情况下执行了send 是否意外在定时任务中使用了自适应send？')
            return

        ws = self.ws

        data: dict = {
            'message_type': self.data.get('message_type'),
            'user_id': self.data.get('target_id'),
            'group_id': self.data.get('group_id'),
            'message': message if isinstance(message, str) else json.dumps(message)
        }

        if auto_escape:
            data['auto_escape'] = auto_escape
        if recall_duration:
            data['recall_duration'] = recall_duration

        return self.action('send_msg',
                           data,
                           echo_needed=echo_needed,
                           timeout=timeout)

    def send_private(self, user_id: int, message: str | dict | list, auto_escape: bool = False,
                     recall_duration: int = None, *, echo_needed: bool = False, timeout=5) -> None | dict:
        """
        发送私聊消息

        :param user_id: QQ号
        :param message: 消息内容，可以是CQ码或是消息段/消息段组合 文档：https://whitechi73.github.io/OpenShamrock/message/format.html#%E7%BB%84%E5%90%88
        :param auto_escape: 是否解析CQ码（True为不解析）
        :param recall_duration: 自动撤回时间间隔（毫秒）
        :param echo_needed: 是否需要等待响应 默认不等待
        :param timeout: 等待响应的秒数
        :return: 当接收到响应时返回响应（message_id: int 消息 ID, time: int64 时间戳） 无响应时返回None
        """

        ws = self.ws

        data: dict = {
            'user_id': user_id,
            'message': message if isinstance(message, str) else json.dumps(message)
        }

        if auto_escape:
            data['auto_escape'] = auto_escape
        if recall_duration:
            data['recall_duration'] = recall_duration

        return self.action('send_private_msg',
                           data,
                           echo_needed=echo_needed,
                           timeout=timeout)

    def send_group(self, group_id: int, message: str | dict | list, auto_escape: bool = False,
                   recall_duration: int = None, *, echo_needed: bool = False, timeout=5) -> None | dict:
        """
        发送群聊消息

        :param group_id: 群号
        :param message: 消息内容，可以是CQ码或是消息段/消息段组合 文档：https://whitechi73.github.io/OpenShamrock/message/format.html#%E7%BB%84%E5%90%88
        :param auto_escape: 是否解析CQ码（True为不解析）
        :param recall_duration: 自动撤回时间间隔（毫秒）
        :param echo_needed: 是否需要等待响应 默认不等待
        :param timeout: 等待响应的秒数
        :return: 当接收到响应时返回响应（message_id: int 消息 ID, time: int64 时间戳） 无响应时返回None
        """

        ws = self.ws

        data: dict = {
            'group_id': group_id,
            'message': message if isinstance(message, str) else json.dumps(message)
        }

        if auto_escape:
            data['auto_escape'] = auto_escape
        if recall_duration:
            data['recall_duration'] = recall_duration

        return self.action('send_group_msg',
                           data,
                           echo_needed=echo_needed,
                           timeout=timeout)

    def group_whole_ban(self, group_id: int, enable: bool = True) -> None:
        """
        设置全体禁言

        :param group_id: 群号
        :param enable: 是否打开全体禁言
        :return:
        """
        return self.action('set_group_whole_ban',
                           {'group_id': group_id, 'enable': enable})


# 命令装饰器
def bot_command(command, *, permission: Callable[[CheckPermission], bool] = lambda sender: True):
    """

    :param command: 命令的触发关键词
    :param permission: 一个接收CheckPermission类的函数，返回值决定了触发关键词时这条命令是否执行。不添加时默认所有人在所有环境里都可以触发
    :return:
    """

    def decorator(func):
        # 标记函数为一条命令
        func._bot_command = command
        func._permission = permission
        return func

    return decorator


# 定时任务装饰器
def scheduled_job(*, every: int = 1, freq: str = ..., at: str = None):
    """

    :param every: 每 n freq执行
    :param freq: day, hour, minute 或 second
    :param at: 只有在 day 和 hour 可以使用。用于在特定时间点执行 day时格式必须为 HH:MM hour时格式必须为 :MM
    :return:
    """

    def decorator(func):
        # 给函数添加一个特定的属性，而不是立即注册
        func._scheduled_job = True
        func._every = every
        func._freq = freq
        func._at = at
        return func

    return decorator


def echo_check(data: dict):
    echo = data.get('echo')
    # 检查echo存在性 顺带一提含echo的信息没有post_type
    if echo and echo in echo_events:
        # 将特定echo返回的信息加入独立队列
        echo_events[echo]["queue"].put(data)

        # 停止send_event线程的阻塞
        echo_events[echo]["event"].set()

        return True
