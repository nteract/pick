import json
import click


def unpack_messages(data):
    all_websocket_messages = []

    for entry in data["log"]["entries"]:
        if "_webSocketMessages" in entry:
            # We have a collection of websocket messages
            for message in entry["_webSocketMessages"]:
                # Now we can deserialize the kernel message
                clean_message = {
                    "payload": json.loads(message["data"]),
                    "type": message["type"],
                    "time": message["time"],
                }
                all_websocket_messages.append(clean_message)
    return all_websocket_messages


@click.command()
@click.argument("input_har", type=click.File("r"))
@click.argument("output_json", type=click.File("w"))
def unpack(input_har, output_json):
    data = json.load(input_har)

    unpack_messages(data)

    json.dump(all_websocket_messages, output_json, indent=4)


if __name__ == "__main__":
    unpack()

