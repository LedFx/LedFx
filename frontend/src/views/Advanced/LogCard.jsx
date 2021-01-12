import React, { useState } from 'react';
import { makeStyles } from '@material-ui/core/styles';
import {
    Card,
    CardHeader,
    CardContent,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Button,
} from '@material-ui/core';
import Typography from '@material-ui/core/Typography';
import ExpandMoreIcon from '@material-ui/icons/ExpandMore';
import { Delete, Refresh } from '@material-ui/icons';

const { LazyLog } = require('react-lazylog');
const { NODE_ENV } = process.env;
const { hostname, port } = window.location;

const wsBaseUrl = NODE_ENV === 'development' ? 'localhost:8888' : `${hostname}:${port}`;
const useStyles = makeStyles({
    content: {
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
    },
    saved: {
        backgroundColor: '#222222',
        padding: '2rem',
        fontFamily: '"Monaco", monospace',
        fontSize: '12px',
        width: '100%',
    },
    lineno: {
        color: '#999',
        width: '35px',
        marginRight: '1rem',
        textAlign: 'right',
        display: 'inline-block',
    },
    linetime: {
        color: '#999',
    },
    root: {
        flexWrap: 'wrap',
    },
    bar: {
        width: '100%',
        display: 'flex',
        justifyContent: 'space-between',
        margin: '0.5rem',
    },
});
const ws_log_url = `ws://${wsBaseUrl}/api/log`;
let socket = null;
const LogCard = ({ settings, error }) => {
    const classes = useStyles();

    const [logger, setLogger] = useState(JSON.parse(window.sessionStorage.getItem('logger')) || []);
    const [clearLogger, setClearLogger] = useState(false);
    return (
        <Card>
            <CardHeader title="Console" subheader="View the Console" />
            <CardContent className={classes.content}>
                <Accordion expanded={true}>
                    <AccordionSummary aria-controls="panel1a-content" id="panel1a-header">
                        <Typography className={classes.heading}>Realtime-Console</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <div style={{ minHeight: 300, width: '100%' }}>
                            <div style={{ height: 300 }}>
                                <LazyLog
                                    enableSearch
                                    url={ws_log_url}
                                    value={'hi'}
                                    websocket
                                    follow
                                    websocketOptions={{
                                        onClose: () => {
                                            if (socket) {
                                                return;
                                            }
                                        },

                                        onOpen: (e, sock) => {
                                            socket = sock;
                                            sock.send(
                                                JSON.stringify({ message: 'Logger Websocket Open' })
                                            );
                                        },
                                        formatMessage: e => {
                                            const line = `${JSON.parse(e).levelno === 10
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
                                                }[${JSON.parse(e).levelname}] \u001b[37m${JSON.parse(e).name
                                                } : ${JSON.parse(e).message}`;
                                            const saveLine = {
                                                levelno: JSON.parse(e).levelno,
                                                levelname: JSON.parse(e).levelname,
                                                message: JSON.parse(e).message,
                                                asctime: JSON.parse(e).asctime,
                                            };
                                            // setLogger[(...logger, saveLine]);
                                            let log = logger;

                                            if (clearLogger) {
                                                window.sessionStorage.removeItem('logger');
                                                setLogger([]);
                                                setClearLogger(false);
                                                log = [];
                                            } else {
                                                window.sessionStorage.setItem(
                                                    'logger',
                                                    JSON.stringify(
                                                        log.slice(log.length - 30, log.length)
                                                    )
                                                );
                                            }
                                            log.push(saveLine);

                                            return line;
                                        },
                                    }}
                                />
                            </div>
                        </div>
                    </AccordionDetails>
                </Accordion>
                <Accordion>
                    <AccordionSummary
                        expandIcon={<ExpandMoreIcon />}
                        aria-controls="panel2a-content"
                        id="panel2a-header"
                    >
                        <Typography className={classes.heading}>SavedLogs-Console</Typography>
                    </AccordionSummary>
                    <AccordionDetails className={classes.root}>
                        <div className={classes.bar}>
                            <Typography className={classes.heading}>
                                Showing last 30 saved log-messages
                            </Typography>
                            <div>
                                <Button
                                    size="small"
                                    startIcon={<Delete />}
                                    variant="contained"
                                    onClick={() => {
                                        window.sessionStorage.removeItem('logger');
                                        setLogger(null);
                                        setClearLogger(true);
                                    }}
                                >
                                    Clear
                                </Button>
                                <Button
                                    size="small"
                                    startIcon={<Refresh />}
                                    variant="contained"
                                    onClick={() => {
                                        setLogger(
                                            JSON.parse(window.sessionStorage.getItem('logger'))
                                        );
                                    }}
                                >
                                    REFRESH
                                </Button>
                            </div>
                        </div>
                        <div className={classes.saved}>
                            {logger &&
                                logger.length > 0 &&
                                logger.map((l, i) => (
                                    <div key={i}>
                                        <span className={classes.lineno}>{i + 1}</span>{' '}
                                        <span className={classes.linetime}>{l.asctime}</span> | [
                                        <span
                                            style={{
                                                color:
                                                    l.levelno === 10
                                                        ? 'purple'
                                                        : l.levelno === 20
                                                            ? 'cyan'
                                                            : l.levelno === 30
                                                                ? 'yellow'
                                                                : l.levelno === 40
                                                                    ? 'orange'
                                                                    : l.levelno === 50
                                                                        ? 'red'
                                                                        : 'green',
                                            }}
                                        >
                                            {l.levelname}
                                        </span>
                                        ] {l.message}
                                    </div>
                                ))}
                        </div>
                    </AccordionDetails>
                </Accordion>
            </CardContent>
        </Card>
    );
};

export default LogCard;
