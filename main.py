import importlib
import pkgutil
import time
import websocket
import threading
import json
import action
import logging
import schedule

# 配置日志
logging.basicConfig(level=logging.DEBUG,
                    format='[%(asctime)s] [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

command_reg = {}


# 动态加载并筛选函数
def load_plugins(ws: websocket.WebSocket):
    plugins_path = 'plugins'
    for _, name, _ in pkgutil.iter_modules([plugins_path]):
        imported_module = importlib.import_module(f"{plugins_path}.{name}")
        # 检查模块中的每个成员
        for attribute_name in dir(imported_module):
            attribute = getattr(imported_module, attribute_name)
            if callable(attribute) and hasattr(attribute, '_scheduled_job'):

                job = schedule.every(getattr(attribute, '_every'))

                freq = getattr(attribute, '_freq')
                match freq:
                    case 'day':
                        if getattr(attribute, '_every') > 1:
                            job = job.days
                        else:
                            job = job.day

                        if getattr(attribute, '_at'):
                            job = job.at(getattr(attribute, '_at'))

                    case 'hour':
                        if getattr(attribute, '_every') > 1:
                            job = job.hours
                        else:
                            job = job.hour

                        if getattr(attribute, '_at'):
                            job = job.at(getattr(attribute, '_at'))

                    case 'minute':
                        if getattr(attribute, '_every') > 1:
                            job = job.minutes
                        else:
                            job = job.minute

                    case 'second':
                        if getattr(attribute, '_every') > 1:
                            job = job.seconds
                        else:
                            job = job.second

                    case _:
                        logging.warning(f"定时任务 '{attribute_name}' 的时间表无效")
                        continue

                job.do(attribute, session=action.Command(ws))
                logging.info(f"定时任务 {attribute_name} 已加载")

            elif callable(attribute) and hasattr(attribute, '_bot_command'):
                command = getattr(attribute, '_bot_command')
                if command not in command_reg:
                    permission = getattr(attribute, '_permission')
                    command_reg[command] = {'func': attribute, 'perm': permission}
                    logging.info(f"命令 {command} 已加载")
                else:
                    logging.warning(f"命令 '{command}' 在 {name} 模块中被重复定义")
        logging.info(f"模块 {name} 已加载")


def on_message(ws: websocket.WebSocket, data):
    data: dict = json.loads(data)

    logging.debug(data)

    if not action.echo_check(data) and not ('echo' in data):
        # 比对信息类型
        match data["post_type"]:
            # 元信息类型
            case "meta_event":
                match data["meta_event_type"]:
                    case "lifecycle":
                        logging.info('新的生命周期')

                    case "heartbeat":
                        logging.debug(f'接收到心跳 echo队列长度为 {len(action.echo_events)}')

                    case _:
                        logging.info("Received:", data)

            # 提示类型
            case 'notice':
                match data['notice_type']:
                    case 'group_recall':
                        threading.Thread(target=recall_message,
                                         args=(ws, data)).start()

                    case _:
                        logging.info("Received:", data)

            # 消息类型
            case "message":
                match data['message_type']:
                    # 私聊消息
                    case "private":
                        threading.Thread(target=private_message,
                                         args=(ws, data)).start()
                    # 群聊消息
                    case "group":
                        threading.Thread(target=group_message,
                                         args=(ws, data)).start()
                    case _:
                        logging.info("Received:", data)

            case _:
                logging.info("Received:", data)


def command_handler(ws: websocket.WebSocket, data: dict, *, is_group: bool = False) -> None:
    # 切片信息
    message: list = data["raw_message"].split(' ')

    if not message[0]:
        return

    if is_group and GROUP_CHAT_REQUIRE_AT:
        if isinstance(data['message'], list):
            if data['message'][0] == {'data': {'qq': '3528019695'}, 'type': 'at'}:
                message.pop(0)

            else:
                logging.debug(f'用户未@我 忽略')
                return

        else:
            logging.debug(f'用户未@我 忽略')
            return

    # 检查命令是否以特定标识开头
    if COMMAND_START:
        if message[0][0] == COMMAND_START and message[0][1:] in command_reg:
            if command_reg[message[0][1:]]['perm'](action.CheckPermission(data)):
                command_reg[message[0][1:]]['func'](action.Command(ws, data))

                logging.info(f'运行命令 {message[0][1:]}')
                return

            else:
                logging.info(f'未达到命令 {message[0][1:]} 的执行条件')
                return

        else:
            logging.debug(f'{message[0]} 不是一条命令')
            return

    elif message[0] in command_reg:
        if command_reg[message[0]]['perm'](action.CheckPermission(data)):
            command_reg[message[0]]['func'](action.Command(ws, data))

            logging.info(f'运行命令 {message[0]}')
            return

        else:
            logging.info(f'未达到命令 {message[0]} 的执行条件')
            return

    else:
        logging.debug(f'{message[0]} 不是一条命令')
        return


def recall_message(ws: websocket.WebSocket, data: dict) -> None:
    user_info = action.Command(ws, data).action('get_group_member_info', {'group_id': data['group_id'], 'user_id': data['operator_id']})

    logging.info(
        f'群 {action.Command(ws, data).action("get_group_info", {"group_id": data["group_id"]})["data"]["group_name"]}({data["group_id"]}) 内 \
{user_info["data"]["nickname"] if not user_info["data"]["card"] else user_info["data"]["card"]}({data["user_id"]}) 撤回消息 ID: {data["message_id"]}')


# 处理私聊消息
def private_message(ws: websocket.WebSocket, data: dict) -> None:
    logging.info(
        f'收到好友 {data["sender"]["nickname"]}({data["sender"]["user_id"]}) 的消息： {data["raw_message"]} ({data["message_id"]})')

    command_handler(ws, data)


# 处理群聊消息
def group_message(ws: websocket.WebSocket, data: dict) -> None:
    logging.info(
        f'收到群 {action.Command(ws, data).action("get_group_info", {"group_id": data["group_id"]})["data"]["group_name"]}({data["group_id"]}) 内 \
{data["sender"]["nickname"] if not data["sender"]["card"] else data["sender"]["card"]}({data["sender"]["user_id"]}) 的消息: {data["raw_message"]} ({data["message_id"]})')

    command_handler(ws, data, is_group=True)


def on_error(ws, error):
    print("Error:", error)


def on_close(ws, close_status_code, close_msg):
    schedule_task.stop()
    print("### closed ###")


def on_open(ws: websocket.WebSocket):
    load_plugins(ws)
    connected_event.set()


class ScheduleCheck(threading.Thread):
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            schedule.run_pending()
            threading.Event().wait(1)
        logging.info('定时任务已停止')


def main():
    # 创建 WebSocket 对象
    ws = websocket.WebSocketApp(websocket_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)

    # 在新线程中运行 WebSocket 客户端
    thread = threading.Thread(target=ws.run_forever)
    thread.start()

    # 等连上了再执行后续代码
    connected_event.wait()

    schedule_task.start()

    try:
        while True:
            # 减少占用
            threading.Event().wait(1)

    except KeyboardInterrupt:
        ws.close()
        print("WebSocket closed")


# WebSocket URL
websocket_url: str = "ws://192.168.3.211:5801"
connected_event = threading.Event()
schedule_task = ScheduleCheck()

COMMAND_START: str = '/'
GROUP_CHAT_REQUIRE_AT: bool = False

if __name__ == '__main__':
    main()
