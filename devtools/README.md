# Devtools

`unpack-har.py` will take a HAR file with Jupyter websocket messages and produce an easier to work with JSON file of just the websocket messages in this format:

```
{
    "message": {
        "header": {
            "msg_id": "55f747b71a324c8f8aff32b77174ea59",
            "username": "username",
            "session": "00f9e2047f51428289b37ee7e40a3e70",
            "msg_type": "kernel_info_request",
            "version": "5.2"
        },
        "metadata": {},
        "content": {},
        "buffers": [],
        "parent_header": {},
        "channel": "shell"
    },
    "type": "send",
    "time": 1603477338.5674412
},
```

## Getting the HAR

To get the HAR file, open the notebook page with the Network tab open in the chrome console. Do everything you want to capture, then select "WS" and right click on the channels and click "Save all as HAR with content".

![image](https://user-images.githubusercontent.com/836375/97236537-89dc7780-17a2-11eb-8233-1a383e55a770.png)
