import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
const { LazyLog } = require('react-lazylog');

const useStyles = makeStyles({
    content: {
        display: 'flex',
        flexDirection: 'column',
    },
});
const url = 'ws://127.0.0.1:8888/api/log';
let socket = null;
const LogCard = ({ settings, error }) => {
    const classes = useStyles();
    console.log('socket:', socket);
    return (
        <Card>
            <CardHeader title="Console" subheader="View the Console" />
            <CardContent className={classes.content}>
                <div>
                    <div style={{ minHeight: 200, width: '100%' }}>
                        <LazyLog
                            enableSearch
                            url={url}
                            websocket
                            websocketOptions={{
                                onOpen: (e, sock) => {
                                    socket = sock;
                                    sock.send(JSON.stringify({ message: 'Logger Websocket Open' }));
                                },
                                formatMessage: e => JSON.parse(e).message,
                            }}
                        />
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default LogCard;
