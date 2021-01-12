import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';

const { LazyLog } = require('react-lazylog');
const { NODE_ENV } = process.env;
const { hostname, port } = window.location;

const wsBaseUrl = NODE_ENV === 'development' ? 'localhost:8888' : `${hostname}:${port}`;
const useStyles = makeStyles({
    content: {
        display: 'flex',
        flexDirection: 'column',
    },
});
const ws_log_url = `ws://${wsBaseUrl}/api/log`;
let socket = null;
const LogCard = ({ settings, error }) => {
    const classes = useStyles();
    console.log('socket:', socket);
    return (
        <Card>
            <CardHeader title="Console" subheader="View the Console" />
            <CardContent className={classes.content}>
                <div>
                    <div style={{ height: 300 }}>
                        <LazyLog
                            enableSearch
                            url={ws_log_url}
                            websocket
                            follow
                            websocketOptions={{
                                onOpen: (e, sock) => {
                                    socket = sock;
                                    sock.send(JSON.stringify({ message: 'Logger Websocket Open' }));
                                },
                                formatMessage: e =>
                                    `${
                                        JSON.parse(e).levelno === 10
                                            ? '\u001b[36m'
                                            : JSON.parse(e).levelno === 20
                                            ? '\u001b[34m'
                                            : JSON.parse(e).levelno === 30
                                            ? '\u001b[33m'
                                            : JSON.parse(e).levelno === 40
                                            ? '\u001b[31m'
                                            : JSON.parse(e).levelno === 50
                                            ? '\u001b[35m'
                                            : '\u001b[32m'
                                    }[${JSON.parse(e).levelname}] \u001b[37m${
                                        JSON.parse(e).name
                                    } : ${JSON.parse(e).message}`,
                            }}
                        />
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default LogCard;
