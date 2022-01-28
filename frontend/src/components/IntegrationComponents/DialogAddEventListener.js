import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
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
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import ListSubheader from '@material-ui/core/ListSubheader';
import FormControl from '@material-ui/core/FormControl';
import Select from '@material-ui/core/Select';
import { Slider, Switch } from '@material-ui/core';
import FormHelperText from '@material-ui/core/FormHelperText';
import ThisDropDown from './DialogAddEventListnerDropDown';
import { createQlcListener } from 'modules/qlc';
//import * as integrationsProxies from 'proxies/integrations';

//To Do:
//useEffect(() => {
//getScenes();
//}, []);

function ConfirmationDialogRaw(props) {
    const { onClose, value: valueProp, open, ...other } = props;
    const [value, setValue] = React.useState(valueProp);
    const [checkButtonType, setButtonType] = React.useState(false);
    const [checkSliderType, setSliderType] = React.useState(false);
    const [checkID, setID] = React.useState(null);
    const [dropDownRenderList, setdropDownRenderList] = React.useState([]);
    const [switchValue, setSwitchValue] = React.useState(false);
    const [sliderValue, setSliderValue] = React.useState(0);
    const [formData, setformData] = React.useState({
        event_type: null,
        event_filter: { scene_name: null },
        qlc_payload: null,
    });
    const [qlcData, setqlcData] = React.useState([]);
    const radioGroupRef = React.useRef(null);
    const [model] = React.useState({});

    const dispatch = useDispatch();
    const qlcInfo = useSelector(state => state.qlc.payload);
    // console.log("qlcInfo - Response: ", qlcInfo);
    //  const effectNames = qlcInfo && qlcInfo.event_types && qlcInfo.event_types.effect_set.event_filters.effect_name
    //const effectCleared = qlcInfo && qlcInfo.event_types && qlcInfo.event_types.effect_cleared.event_name
    const SceneSet =
        qlcInfo && qlcInfo.event_types && qlcInfo.event_types.scene_activated.event_filters.scene_name;
    const QLCWidgets =
        qlcInfo &&
        qlcInfo.qlc_widgets &&
        qlcInfo.qlc_widgets.sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
    // const EVENT_TYPES= qlcInfo && qlcInfo.event_types && qlcInfo.event_types
    // console.log("test3",EVENT_TYPES);
    const qlcStuff = [];
    const qlcID = {};
    //const qlcType = {}
    qlcInfo &&
        qlcInfo.qlc_widgets &&
        qlcInfo.qlc_widgets.map(a => {
            qlcStuff[a[0]] = { id: a[0], Type: a[1], Name: a[2] };
            qlcID[a[0]] = a[1];
            //qlcType[a[0]] = (a[1]);
            return true;
        });

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
        console.log('QLCFormEventTest1', formData);
        const data = JSON.stringify(formData);
        console.log('QLCFormEventTest1', data);
        dispatch(createQlcListener(props.integration.id, formData));
        // props.createQlcListener(props.integration.id,formData);

        // window.location = window.location.href;
    };

    const onModelChange = (key, val) => {
        utils.selectOrSet(key, model, val);
    };

    //const [f, setAge] = React.useState('');
    const handleEventChange = (event, val) => {
        console.log('typetest', event.target);
        let value = event.target.value;
        if (event.target.type === 'checkbox') {
            event.target.checked ? (value = 255) : (value = 0);
            const qlcDatanewArr = qlcData.slice();
            qlcDatanewArr[0][event.target.name] = value;
            let newqlcPayload = Object.assign({}, ...qlcDatanewArr);
            let newSwitchState = {
                ...formData,
                qlc_payload: {
                    ...newqlcPayload,
                },
            };
            setSwitchValue(event.target.checked);
            setqlcData(qlcDatanewArr);
            console.log('test', newSwitchState);
            setformData(newSwitchState);
        } else if (event.target.name === 'qlc_payload') {
            const qlcDatanewArr = qlcData.slice();
            let qlcDataObj = {
                [event.target.value[0]]: 0,
            };
            qlcDatanewArr[0] = qlcDataObj;
            setSwitchValue(false);
            setqlcData(qlcDatanewArr);
            let newqlcPayload = Object.assign({}, ...qlcDatanewArr);

            let newSwitchState = {
                ...formData,
                qlc_payload: {
                    ...newqlcPayload,
                },
            };
            console.log('test', newSwitchState);
            setformData(newSwitchState);
        } else if (event.target.name === 'scene_name') {
            value = JSON.parse(value);
            let newFormState = {
                ...formData,
                event_filter: {
                    ...formData['event_filter'],
                    [event.target.name]: value['event_name'],
                },
                event_type: value['event_type'],
            };
            setformData(newFormState);
        } else {
            // console.log("typetest",val);
            // console.log("typevalue",checkID);
            const qlcDatanewArr = qlcData.slice();
            qlcDatanewArr[0][checkID] = val;
            let newqlcPayload = Object.assign({}, ...qlcDatanewArr);
            let newSliderState = {
                ...formData,
                qlc_payload: {
                    ...newqlcPayload,
                },
            };
            setSliderValue(val);
            setformData(newSliderState);
        }

        // setformData(inputs => ({...inputs, [event.target.name]: event.target.value}));
    };

    const handleTypeChange = event => {
        event.target.value.includes('Button') ? setButtonType(true) : setButtonType(false);
        event.target.value.includes('Slider') ? setSliderType(true) : setSliderType(false);
        setSwitchValue(false);
        setID(event.target.value[0]);
        handleEventChange(event);
    };

    //work here next time to eliminate reference cloning probably make different handleswitchchange
    const handleDropTypeChange = (event, index, val, name) => {
        // console.log("testing1",event.target.value);
        // console.log("testing",dropDownRenderList)
        const newArr = dropDownRenderList.slice();
        if (event.target.name === 'qlc_payload' && event.target.value.includes('Button')) {
            newArr[index].showSwitch = true;
            newArr[index].showSlider = false;
        } else if (event.target.name === 'qlc_payload' && event.target.value.includes('Slider')) {
            newArr[index].showSlider = true;
            newArr[index].showSwitch = false;
        }
        // if(event.target.name === "qlc_payload"){

        // }
        let value = event.target.value;
        if (event.target.type === 'checkbox') {
            newArr[index].switchValue = event.target.checked;
            event.target.checked ? (value = 255) : (value = 0);
            const qlcDatanewArr = qlcData.slice();
            qlcDatanewArr[index + 1][event.target.name] = value;
            let newqlcPayload = Object.assign({}, ...qlcDatanewArr);
            let newSwitchState = {
                ...formData,
                qlc_payload: {
                    ...newqlcPayload,
                },
            };

            setqlcData(qlcDatanewArr);
            setformData(newSwitchState);
        } else if (event.target.name === 'qlc_payload') {
            newArr[index]['value'] = event.target.value[0];
            console.log('test13', newArr);
            const qlcDatanewArr = qlcData.slice();
            let qlcDataObj = {
                [event.target.value[0]]: 0,
            };
            console.log('test0', qlcDataObj);
            if (qlcDatanewArr[index + 1] === undefined) {
                qlcDatanewArr.push(qlcDataObj);
            } else {
                newArr[index].switchValue = false;
                qlcDatanewArr[index + 1] = qlcDataObj;
            }

            setqlcData(qlcDatanewArr);

            let newqlcPayload = Object.assign({}, ...qlcDatanewArr);

            let newSwitchState = {
                ...formData,
                qlc_payload: {
                    ...newqlcPayload,
                },
            };
            console.log('test', newSwitchState);
            setformData(newSwitchState);
        } else {
            const qlcDatanewArr = qlcData.slice();
            qlcDatanewArr[index + 1][name] = val;
            let newqlcPayload = Object.assign({}, ...qlcDatanewArr);
            let newSliderState = {
                ...formData,
                qlc_payload: {
                    ...newqlcPayload,
                },
            };

            setqlcData(qlcDatanewArr);
            setformData(newSliderState);
        }

        return setdropDownRenderList(newArr);
    };

    const handleTypeAddDropDown = event => {
        const newItem = {
            id: Date.now(),
            value: '',
            switchValue: false,
            showSwitch: false,
            showSlider: false,
        };

        const newArr = dropDownRenderList.slice();
        newArr.push(newItem);
        return setdropDownRenderList(newArr);
    };

    const handleTypeRemoveDropDown = idx => {
        const newArr = dropDownRenderList.slice();
        newArr.splice(idx, 1);
        const newQlcData = qlcData.slice();
        newQlcData.splice(idx + 1, 1);
        setqlcData(newQlcData);
        let newqlcPayload = Object.assign({}, ...newQlcData);
        let newSwitchState = {
            ...formData,
            qlc_payload: {
                ...newqlcPayload,
            },
        };
        console.log('test', newSwitchState);
        setformData(newSwitchState);
        return setdropDownRenderList(newArr);
    };

    const marks = [
        { value: 1, label: '1' },
        { value: 255, label: '255' },
    ];

    delete other.deviceList;

    return (
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
                    To add a Event Listener to LedFx, please first select the type of event trigger
                    (If This), and then provide the expected output (Then Do This).
                </DialogContentText>
                <FormControl>
                    <InputLabel htmlFor="grouped-select">Event Trigger (If This)</InputLabel>
                    <Select
                        id="grouped-select"
                        defaultValue={formData['event_filter']['scene_name']}
                        name="scene_name"
                        onChange={handleEventChange}
                    >
                        <MenuItem value="">
                            <em>None</em>
                        </MenuItem>
                        <ListSubheader color="primary">Scene Set</ListSubheader>
                        {SceneSet &&
                            SceneSet.length > 0 &&
                            SceneSet.map((val, idx) => (
                                <MenuItem
                                    key={idx}
                                    value={JSON.stringify({
                                        event_type: 'scene_set',
                                        event_name: val,
                                    })}
                                    name={val}
                                >
                                    <option>{val}</option>
                                </MenuItem>
                            ))}
                        {/* We may want this at a later time.
                        <ListSubheader color="primary">
                            Effect Set
                        </ListSubheader>
                            {effectNames && effectNames.length > 1 && effectNames.map((val,idx)=>
                                <MenuItem
                                    key={idx}
                                    value={JSON.stringify({"event_type":"effect_set","event_name":val})}
                                    name={val}
                                >
                                    <option>
                                       {val}
                                    </option>
                                </MenuItem>)
                            }

                        <ListSubheader color="primary">
                            Effect Cleared
                        </ListSubheader>
                        <MenuItem><option>effect_cleared, effect_name: Effect Cleared</option></MenuItem>*/}
                    </Select>
                </FormControl>
                <FormHelperText>
                    {' '}
                    If you select an existing event trigger, then this will update/replace the
                    existing `Then Do This`.
                </FormHelperText>
                <FormControl>
                    <InputLabel htmlFor="grouped-select">Then Do This</InputLabel>
                    <Select
                        labelId="demo-simple-select-helper-label"
                        id="demo-simple-select-helper"
                        // value={formData.qlc_payload}
                        name="qlc_payload"
                        onChange={handleTypeChange}
                    >
                        <MenuItem value=""></MenuItem>
                        {QLCWidgets &&
                            QLCWidgets.length > 0 &&
                            QLCWidgets.map((e, f) => (
                                <MenuItem key={f} value={e} name={e[0]}>
                                    <option>
                                        ID: {e[0]}, Type: {e[1]}, Name: {e[2]}
                                    </option>
                                    {/* {Object.entries(qlcStuff)}
                            {QLCWidgets && QLCWidgets.length > 0 && QLCWidgets.map((e,f)=><MenuItem key={f} value="">
                            <option>{e}</option>*/}
                                </MenuItem>
                            ))}
                    </Select>

                    {/*
                If {qlcType}  === 'Button' or 'Audio Triggers'
                return switch off (Value: 0) or on (Value: 255)
                If {qlcType}  === 'slider'
                return Slider
                Slider range: (0 to 255)
                    Else hide below buttons.
                */}
                </FormControl>

                {/*    For delete button using delete icon.
                    <Button aria-describedby={id} variant="contained" color="primary" onClick={() => { onDeleteVitem(listItem) }}>
                        <DeleteIcon />
                    </Button>
                    */}

                {/* <div style={{ minWidth: '150px' }}></div> */}
                <div>
                    {checkButtonType && <label>QLC+ widget selected above (On/Off) </label>}
                    {checkButtonType && (
                        <Switch
                            color="primary"
                            // value={!formData.switch_value?255:0}
                            checked={switchValue}
                            name={checkID}
                            onChange={handleEventChange}
                        />
                    )}
                </div>

                <div style={{ minWidth: '150px' }}>
                    {checkSliderType && <label>QLC Slider Widget Value</label>}
                    {checkSliderType && (
                        <Slider
                            aria-labelledby="discrete-slider"
                            valueLabelDisplay="auto"
                            marks={marks}
                            step={1}
                            min={0}
                            max={255}
                            defaultValue={1}
                            value={sliderValue}
                            onChange={handleEventChange}
                        />
                    )}
                </div>
                {dropDownRenderList.map((item, idx) => (
                    <ThisDropDown
                        key={idx}
                        idx={idx}
                        QLCWidgets={QLCWidgets}
                        id={item.id}
                        value={item.value}
                        switchValue={item.switchValue}
                        showSwitch={item.showSwitch}
                        showSlider={item.showSlider}
                        handleDropTypeChange={handleDropTypeChange}
                        handleTypeRemoveDropDown={handleTypeRemoveDropDown}
                    />
                ))}
                {/*
                If Below button pressed, then show additional 'Then do this' dropdown field.
                */}
                <Button
                    variant="contained"
                    color="primary"
                    aria-label="Add"
                    endIcon={<AddCircleIcon />}
                    // aria-haspopup="true"
                    // integrationsProxies.deleteIntegration(data);
                    onClick={handleTypeAddDropDown}
                    role="listitem"
                >
                    ADD additional 'then do this'
                </Button>

                <SchemaForm
                    // className={classes.schemaForm}
                    schema={{
                        type: 'object',
                        title: 'Configuration',
                        properties: {},
                        ...{
                            /*(integrationTypes ? integrationTypes[integration].schema : {})*/
                        },
                    }}
                    /*(form={
                        integrationTypes[integration] &&
                        integrationTypes[integration].schema.required

                        Line 413 backup <Button onClick={console.log("QLCFormEventTest",formData)} color="primary">
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
    // const dispatch = useDispatch();
    //console.log("YZ03:", event_types)

    const handleClickListItem = () => {
        setOpen(true);
    };

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
                    // aria-haspopup="true"
                    onClick={handleClickListItem}
                    role="listitem"
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
                    createQlcListener={createQlcListener}
                />
            </>
        </div>
    );
}
