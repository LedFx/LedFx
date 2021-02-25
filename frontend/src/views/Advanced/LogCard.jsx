import React, { useState } from 'react';
import { makeStyles } from '@material-ui/core/styles';
import {
    Card,
    CardHeader,
    CardActions,
    CardContent,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Button,
    TextField,
    FormControlLabel,
    Checkbox,
    IconButton,
} from '@material-ui/core';
import Typography from '@material-ui/core/Typography';
import ExpandMoreIcon from '@material-ui/icons/ExpandMore';
import { Delete } from '@material-ui/icons';
import BugReportIcon from '@material-ui/icons/BugReport';
import { useSelector } from 'react-redux';

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
        overflowX: 'scroll',
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
    wrapping: {
        whiteSpace: 'wrap',
    },
    not_wrapping: {
        whiteSpace: 'nowrap',
    },
});
const ws_log_url = `ws://${wsBaseUrl}/api/log`;
let socket = null;
const LogCard = ({ settings, error }) => {
    const classes = useStyles();
    const [logger, setLogger] = useState(JSON.parse(window.sessionStorage.getItem('logger')) || []);
    const [logLength, setLogLength] = useState(
        JSON.parse(window.sessionStorage.getItem('messages')) || 30
    );
    const [wrap, setWrap] = useState(false);
    const settings2 = useSelector(state => state.settings);
    return (
        <Card>
            <CardHeader title="Tools" subheader="for advanced users only" />
            <CardContent className={classes.content}>
                {parseInt(window.localStorage.getItem('BladeMod')) > 1 ? (
                    <>
                        <Accordion>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />} aria-controls="panel1a-content" id="panel1a-header">
                                <Typography className={classes.heading}>
                                    Realtime-Console
                                </Typography>
                            </AccordionSummary>

                            <AccordionDetails className={classes.root}>
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
                                                        JSON.stringify({
                                                            message: 'Logger Websocket Open',
                                                        })
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

                                                    const log =
                                                        JSON.parse(
                                                            window.sessionStorage.getItem('logger')
                                                        ) || [];
                                                    log.push(saveLine);
                                                    const test = log.slice(
                                                        log.length > logLength - 1
                                                            ? log.length - logLength
                                                            : 0,
                                                        log.length
                                                    );
                                                    setLogger(test);

                                                    window.sessionStorage.setItem(
                                                        'logger',
                                                        JSON.stringify(test)
                                                    );

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
                                <Typography className={classes.heading}>
                                    SavedLogs-Console
                                </Typography>
                            </AccordionSummary>
                            <AccordionDetails className={classes.root}>
                                <div className={classes.bar}>
                                    <Typography className={classes.heading}></Typography>
                                    <div
                                        style={{
                                            display: 'flex',
                                            justifyContent: 'center',
                                            alignItems: 'center',
                                        }}
                                    >
                                        <Button
                                            size="large"
                                            style={{ marginRight: '1rem' }}
                                            startIcon={<Delete />}
                                            variant="text"
                                            onClick={() => {
                                                window.sessionStorage.removeItem('logger');
                                                setLogger([]);
                                            }}
                                        ></Button>
                                        <FormControlLabel
                                            value="top"
                                            control={
                                                <Checkbox
                                                    color="primary"
                                                    checked={wrap}
                                                    onChange={() => setWrap(!wrap)}
                                                    style={{ padding: '2px 8px 13px' }}
                                                />
                                            }
                                            labelPlacement="top"
                                            label={
                                                <span style={{ fontSize: '0.7rem', color: '#bbb' }}>
                                                    Wrap
                                                </span>
                                            }
                                        />
                                        <TextField
                                            id="standard-number"
                                            label="Stored logs"
                                            style={{ minWidth: '90px' }}
                                            defaultValue={logLength}
                                            onChange={e => {
                                                window.sessionStorage.setItem(
                                                    'messages',
                                                    e.target.value
                                                );
                                                setLogLength(e.target.value);
                                            }}
                                            type="number"
                                            InputLabelProps={{
                                                shrink: true,
                                            }}
                                            InputProps={{
                                                inputProps: {
                                                    min: 0,
                                                    max: 100,
                                                    style: { textAlign: 'center' },
                                                },
                                            }}
                                        />
                                    </div>
                                </div>
                                <div className={classes.saved}>
                                    {logger &&
                                        logger.length > 0 &&
                                        logger.map((l, i) => (
                                            <div
                                                key={i}
                                                className={
                                                    wrap ? classes.wrapping : classes.not_wrapping
                                                }
                                            >
                                                <span className={classes.lineno}>{i + 1}</span>{' '}
                                                <span className={classes.linetime}>
                                                    {l.asctime}
                                                </span>{' '}
                                                | [
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
                                                ]{' '}
                                                <span
                                                    style={{
                                                        color: '#fff',
                                                    }}
                                                >
                                                    {l.message}
                                                </span>
                                            </div>
                                        ))}
                                </div>
                            </AccordionDetails>
                        </Accordion>
                    </>
                ) : (
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

                                            const log =
                                                JSON.parse(window.sessionStorage.getItem('logger')) ||
                                                [];
                                            log.push(saveLine);
                                            const test = log.slice(
                                                log.length > logLength - 1 ? log.length - logLength : 0,
                                                log.length
                                            );
                                            setLogger(test);

                                            window.sessionStorage.setItem(
                                                'logger',
                                                JSON.stringify(test)
                                            );

                                            return line;
                                        },
                                    }}
                                />
                            </div>
                        </div>
                    )}
            </CardContent>
            <CardActions style={{ justifyContent: 'flex-end' }}>
                {logger.length > 2 && (
                    <IconButton
                        aria-label="BugTracker"
                        color="inherit"
                        onClick={() => {
                            const message = `
<!---ENTER A TITLE--->
<!---DESCRIBE YOUR ISSUE IN DETAIL--->


<!---DON'T TOUCH THE REST - JUST CLICK PREVIEW--->
## Settings:
\`\`\`json
${JSON.stringify(settings2, null, 2)}
\`\`\`


## userAgent:
\`\`\`json
${navigator.userAgent.replaceAll(';', '-')}
\`\`\`

## Logs:
\`\`\`json
${JSON.stringify(
                                logger.map(l => l.message).filter((v, i, a) => a.indexOf(v) === i),
                                null,
                                2
                            )}
\`\`\`
    `;
                            window.open(
                                `https://github.com/LedFx/LedFx/issues/new?body=${encodeURIComponent(
                                    message
                                )}`
                            );
                        }}
                        target="_blank"
                        title="BugTracker"
                    >
                        <BugReportIcon />
                    </IconButton>
                )}
            </CardActions>
        </Card>
    );
};

export default LogCard;
