import importlib
import pkgutil
import websocket
import threading
import json
import action
import logging

# 配置日志
logging.basicConfig(level=logging.DEBUG,
                    format='[%(asctime)s] [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

command_reg = {}


# 动态加载并筛选函数
def load_plugins():
    plugins_path = 'plugins'
    for _, name, _ in pkgutil.iter_modules([plugins_path]):
        imported_module = importlib.import_module(f"{plugins_path}.{name}")
        # 检查模块中的每个成员
        for attribute_name in dir(imported_module):
            attribute = getattr(imported_module, attribute_name)
            if callable(attribute) and hasattr(attribute, '_bot_command'):
                command = getattr(attribute, '_bot_command')
                if command not in command_reg:
                    command_reg[command] = attribute
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


# 处理私聊消息
def private_message(ws: websocket.WebSocket, data: dict) -> None:
    logging.info(
        f'收到好友 {data["sender"]["nickname"]}({data["sender"]["user_id"]}) 的消息： {data["raw_message"]} ({data["message_id"]})')

    if data["raw_message"] in command_reg:
        command_reg[data["raw_message"]](action.Command(ws, data))
    else:
        print(f"未知命令: {data["raw_message"]}")


# 处理群聊消息
def group_message(ws: websocket.WebSocket, data: dict) -> None:
    logging.info(
        f'收到群 {action.Command(ws, data).action("get_group_info", {"group_id": data["group_id"]})["data"]["group_name"]}({data["group_id"]}) 内 \
{data["sender"]["nickname"] if not data["sender"]["card"] else data["sender"]["card"]}({data["sender"]["user_id"]}) 的消息: {data["raw_message"]} ({data["message_id"]})')

    if data["raw_message"] in command_reg:
        command_reg[data["raw_message"]](action.Command(ws, data))
    else:
        print(f"未知命令: {data["raw_message"]}")


def on_error(ws, error):
    print("Error:", error)


def on_close(ws, close_status_code, close_msg):
    print("### closed ###")


def on_open(ws):
    load_plugins()
    connected_event.set()


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

    try:
        while True:
            # 减少占用
            threading.Event().wait(1)
    except KeyboardInterrupt:
        ws.close()
        print("WebSocket closed")


# WebSocket URL
websocket_url = "ws://192.168.3.211:5801"
connected_event = threading.Event()

if __name__ == '__main__':
    main()
