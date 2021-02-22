import React, { useState } from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
import Check from '@material-ui/icons/Check';
import Warning from '@material-ui/icons/Warning';
import Info from '@material-ui/icons/Info';
import {
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Button,
} from '@material-ui/core';
import Typography from '@material-ui/core/Typography';
import ExpandMoreIcon from '@material-ui/icons/ExpandMore';
import ConfigEditor from './ConfigEditor';

import MuiAlert from '@material-ui/lab/Alert';
import Snackbar from '@material-ui/core/Snackbar';
import GradientCard from './GradientCard';
import MatrixCard from './MatrixCard';
import TransitionCard from './TransitionCard';
function Alert(props) {
    return <MuiAlert elevation={6} variant="filled" {...props} />;
}
const useStyles = makeStyles({
    content: {
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
    },
})

const DevCard = ({ settings, error }) => {

    const classes = useStyles();
    const [snackbarState, setSnackbarState] = useState({ open: false, message: '', type: 'error' });

    const handleClose = () => {
        setSnackbarState({ ...snackbarState, open: false });
    };
    return (
        <>
            <Card style={{ margin: '2rem 0', overflow: 'unset' }}>
                <CardHeader title="Dev Area" subheader="for developers only" />
                <CardContent>
                    <Accordion>
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            aria-controls="notifcation-buttons-content"
                            id="notifcation-buttons-header"
                        >
                            <Typography className={classes.heading}>
                                Notification Buttons
                                </Typography>
                        </AccordionSummary>
                        <AccordionDetails className={classes.root}>
                            <Button
                                size="small"
                                startIcon={<Warning />}
                                variant="contained"
                                style={{ marginRight: '10px' }}
                                onClick={() => {
                                    setSnackbarState({
                                        ...snackbarState,
                                        message: 'TEST ERROR',
                                        open: true,
                                    });
                                }}
                            >
                                Error Message
                                </Button>
                            <Button
                                size="small"
                                startIcon={<Check />}
                                variant="contained"
                                style={{ marginRight: '10px' }}
                                onClick={() => {
                                    setSnackbarState({
                                        ...snackbarState,
                                        message: 'TEST SUCCESS',
                                        open: true,
                                        type: 'success',
                                    });
                                }}
                            >
                                Success Message
                                </Button>
                            <Button
                                size="small"
                                startIcon={<Warning />}
                                style={{ marginRight: '10px' }}
                                variant="contained"
                                onClick={() => {
                                    setSnackbarState({
                                        ...snackbarState,
                                        message: 'TEST WARNING',
                                        open: true,
                                        type: 'warning',
                                    });
                                }}
                            >
                                Warning Message
                                </Button>
                            <Button
                                size="small"
                                startIcon={<Info />}
                                variant="contained"
                                onClick={() => {
                                    setSnackbarState({
                                        ...snackbarState,
                                        message: 'TEST INFO',
                                        open: true,
                                        type: 'info',
                                    });
                                }}
                            >
                                Info Message
                                </Button>
                        </AccordionDetails>
                    </Accordion>

                    <Accordion>
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            aria-controls="config-editor-content"
                            id="config-editor-header"
                        >
                            <Typography className={classes.heading}>
                                Config Editor
                                </Typography>
                        </AccordionSummary>
                        <AccordionDetails className={classes.root}>
                            <ConfigEditor raw />
                        </AccordionDetails>
                    </Accordion>
                    <Accordion>
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            aria-controls="gradient-content"
                            id="gradient-header"
                        >
                            <Typography className={classes.heading}>
                                GradientGenerator - POC
                                </Typography>
                        </AccordionSummary>
                        <AccordionDetails className={classes.root}>
                            <GradientCard />
                        </AccordionDetails>
                    </Accordion>
                    <Accordion>
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            aria-controls="2d-content"
                            id="2d-header"
                        >
                            <Typography className={classes.heading}>
                                2D - Matrix - POC
                                </Typography>
                        </AccordionSummary>
                        <AccordionDetails className={classes.root}>
                            <MatrixCard />
                        </AccordionDetails>
                    </Accordion>
                    <Accordion>
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            aria-controls="transition-content"
                            id="transition-header"
                        >
                            <Typography className={classes.heading}>
                                Transition - POC
                                </Typography>
                        </AccordionSummary>
                        <AccordionDetails className={classes.root}>
                            <TransitionCard />
                        </AccordionDetails>
                    </Accordion>
                </CardContent>
            </Card>
            <Snackbar
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
                autoHideDuration={1000 + snackbarState.message.length * 60}
                open={snackbarState.open}
                onClose={handleClose}
                key={'bottomcenter'}
            >
                <Alert severity={snackbarState.type}>{snackbarState.message}</Alert>
            </Snackbar>
        </>
    );
};

export default DevCard;
