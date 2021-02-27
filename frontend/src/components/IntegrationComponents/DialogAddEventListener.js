import React from 'react'; //, { useEffect, useState }
//import {useDispatch } from 'react-redux'; //useSelector,
import PropTypes from 'prop-types';
import { makeStyles } from '@material-ui/core/styles';
import Button from '@material-ui/core/Button';
import DialogTitle from '@material-ui/core/DialogTitle';
import DialogContent from '@material-ui/core/DialogContent';
import DialogActions from '@material-ui/core/DialogActions';
import Dialog from '@material-ui/core/Dialog';
import AddCircleIcon from '@material-ui/icons/AddCircle';
import { SchemaForm, utils } from 'react-schema-form';
import DialogContentText from '@material-ui/core/DialogContentText';
import DropDown from 'components/forms/DropDown';
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
//import ListSubheader from '@material-ui/core/ListSubheader';
import FormControl from '@material-ui/core/FormControl';
import Select from '@material-ui/core/Select';
import { Slider, Switch } from '@material-ui/core';

function ConfirmationDialogRaw(props) {
    const { onClose, value: valueProp, open, ...other } = props;
    const [value, setValue] = React.useState(valueProp);
    const radioGroupRef = React.useRef(null);
    const [model] = React.useState({});

    React.useEffect(() => {
        if (!open) {
            setValue(valueProp);
        }
    }, [valueProp, open]);

    const handleEntering = () => {
        if (radioGroupRef.current != null) {
            radioGroupRef.current.focus();
        }
    };

    const handleCancel = () => {
        onClose();
    };

    const handleOk = () => {
        onClose(value);
        window.location = window.location.href;
    };

    const classes = useStyles();

    const onModelChange = (key, val) => {
        utils.selectOrSet(key, model, val);

    };
    delete other.deviceList;
    return (
        console.log('MattTestDropdown Get: QLCInfo', ),
        <Dialog
            disableBackdropClick
            disableEscapeKeyDown
            maxWidth="xs"
            onEntering={handleEntering}
            aria-labelledby="confirmation-dialog-title"
            open={open}
            {...other}
        >
            <DialogTitle id="confirmation-dialog-title">
                Event Listener Setup: {props.integration.id}

            </DialogTitle>
            <DialogContent dividers>
                <DialogContentText>
                    To add a Event Listener to LedFx, please first select the type of event trigger (If This),
                    and then provide the expected output (Then That).
                </DialogContentText>
                <FormControl className={classes.FormRow}>
                    <InputLabel htmlFor="grouped-select">Event Trigger (If This)</InputLabel>
                    <Select
                    //defaultValue={props.event_types}
                    //onChange={onEffectTypeChange}
                    id="grouped-select"
                    className={classes.FormSelect}
                >
                    {/*From Redux: qlclistener_add, show dropdown event_types*/}
                        <MenuItem value="">
                            <em>None</em>
                        </MenuItem>
                        {/*
                        {event_types &&
                        Object.keys(group).map(
                            c =>
                                formats.indexOf(c) !== -1 && [
                                    <ListSubheader
                                        className={classes.FormListHeaders}
                                        color="primary"
                                    >
                                        {c}
                                    </ListSubheader>,
                                    group[c].map(e => <MenuItem value={e.id}>{e.name}</MenuItem>),
                                ]
                        )}
                        */}
                        </Select>
                </FormControl>
                <form>
                    <DropDown
                    label="Then Do This"
                    /*From Redux: qlclistener_add, show dropdown qlc_widgets
                    Think we should convert API data from:
                    [
                        "7",
                        "Button",
                        "Button 7"
                    ]
                    to show dropdown feild of 'ID: 7, Button, Button 7' 
                    */
                    />
                </form>

                    {/*
                    Below is  ONLY if QLC+ widget selected above is either 'Button' or 'Audio Triggers'
                    “Buttons” can be set to either off (0) or on (255)
                    “Audio Triggers” are either off (0) or on (255)
                    */}
                    <label>QLC+ widget selected above (On/Off) </label>
                    <Switch color="primary" checked={true} />

                    {/*
                    Below is for ONLY if QLC+ widget selected above is 'slider'
                    */}
                    <div style={{ minWidth: '150px' }}>
                                <label>QLC Slider Widget Value</label>
                                        <Slider
                                            aria-labelledby="discrete-slider"
                                            valueLabelDisplay="auto"
                                            marks
                                            step={1}
                                            min={0}
                                            max={255}
                                            defaultValue={1}
                                        />
                            </div> 
                
                <Button
                    variant="contained"
                    color="primary"
                    aria-label="Add"
                    endIcon={<AddCircleIcon />}
                    aria-haspopup="true"
                    // integrationsProxies.deleteIntegration(data);
                    //onClick={handleClickListItem}
                    //role="listitem"
                >
                    ADD additional 'then do this'
                </Button>
                <SchemaForm
                    // className={classes.schemaForm}
                    schema={{
                        type: 'object',
                        title: 'Configuration',
                        properties: {},
                        ...{/*(integrationTypes ? integrationTypes[integration].schema : {})*/},
                    }}
                    /*(form={
                        integrationTypes[integration] &&
                        integrationTypes[integration].schema.required
                    })*/
                    model={model}
                    onModelChange={onModelChange}
                />
            </DialogContent>
            <DialogActions>
                <Button autoFocus onClick={handleCancel} color="primary">
                    Cancel
                </Button>
                <Button onClick={handleOk} color="primary">
                    Ok
                </Button>
            </DialogActions>
        </Dialog>
    );
}

ConfirmationDialogRaw.propTypes = {
    onClose: PropTypes.func.isRequired,
    open: PropTypes.bool.isRequired,
    value: PropTypes.string.isRequired,
    config: PropTypes.any,
};

const useStyles = makeStyles(theme => ({
    root: {
        width: '100%',
        maxWidth: 360,
        backgroundColor: theme.palette.background.paper,
    },
    paper: {
        width: '80%',
        maxHeight: 535,
    },
}));

export default function ConfirmationDialog({ deviceList, config, integration }) {
    const classes = useStyles();
    const [open, setOpen] = React.useState(false);
    //const dispatch = useDispatch();
    //console.log("YZ03:", integration)
    
    const handleClickListItem = async() => {
        setOpen(true)};

    const handleClose = newValue => {
        setOpen(false);
    };

    return (
        <div className={classes.root}>
            <>
                <Button
                    variant="contained"
                    color="primary"
                    aria-label="Add"
                    className={classes.button}
                    endIcon={<AddCircleIcon />}
                    aria-haspopup="true"
                    onClick={handleClickListItem}
                    //role="listitem"
                >
                    ADD EVENT LISTENER 
                </Button>

                <ConfirmationDialogRaw
                    classes={{
                        paper: classes.paper,
                    }}
                    config={config}
                    id="ringtone-menu"
                    keepMounted
                    open={open}
                    onClose={handleClose}
                    value={integration}
                    deviceList={deviceList}
                    integration={integration}
                />
            </>
        </div>
    );
}
