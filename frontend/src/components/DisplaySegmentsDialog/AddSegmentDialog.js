import React from 'react';
import PropTypes from 'prop-types';
import { makeStyles } from '@material-ui/core/styles';
import Button from '@material-ui/core/Button';
import DialogTitle from '@material-ui/core/DialogTitle';
import DialogContent from '@material-ui/core/DialogContent';
import DialogActions from '@material-ui/core/DialogActions';
import Dialog from '@material-ui/core/Dialog';
import RadioGroup from '@material-ui/core/RadioGroup';
import Radio from '@material-ui/core/Radio';
import FormControlLabel from '@material-ui/core/FormControlLabel';
import AddCircleIcon from '@material-ui/icons/AddCircle';
import { useSelector, useDispatch } from 'react-redux';
import { updateDisplayConfig } from 'modules/displays';

function ConfirmationDialogRaw(props) {
    const { onClose, value: valueProp, open, ...other } = props;
    const [value, setValue] = React.useState(valueProp);
    const radioGroupRef = React.useRef(null);

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
    };

    const handleChange = event => {
        setValue(event.target.value);
    };

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
            <DialogTitle id="confirmation-dialog-title">Select a device</DialogTitle>
            <DialogContent dividers>
                <RadioGroup
                    ref={radioGroupRef}
                    aria-label="ringtone"
                    name="ringtone"
                    value={value}
                    onChange={handleChange}
                >
                    {props.deviceList.map(device => (
                        <FormControlLabel
                            value={device.name}
                            key={device.name}
                            control={<Radio />}
                            label={device.name}
                        />
                    ))}
                </RadioGroup>
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
        margin: '1rem auto',
        backgroundColor: theme.palette.background.paper,
    },
    paper: {
        width: '80%',
        maxHeight: 435,
    },
}));

export default function ConfirmationDialog({ display, config }) {
    const classes = useStyles();
    const [open, setOpen] = React.useState(false);
    const dispatch = useDispatch();
    const deviceList = useSelector(state => state.devices.list) || [];

    const handleClickListItem = () => {
        setOpen(true);
    };

    const handleClose = newValue => {
        setOpen(false);
        if (newValue) {
            const device = { ...deviceList.find(d => d.name === newValue) };
            const temp = [
                ...display.segments,
                [device.id, 0, device.config.pixel_count - 1, false],
            ];
            console.log('1', temp);
            const test = temp.filter(t => console.log('WTF', t) || t.length === 4);
            dispatch(updateDisplayConfig({ id: display.id, data: test }));
        }
    };

    return (
        <div className={classes.root}>
            {deviceList.length > 0 ? (
                <>
                    <Button
                        variant="contained"
                        color="primary"
                        aria-label="Add"
                        className={classes.button}
                        endIcon={<AddCircleIcon />}
                        onClick={handleClickListItem}
                        role="listitem"
                    >
                        ADD SEGMENT
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
                        value={deviceList[0].name}
                        deviceList={deviceList}
                    />
                </>
            ) : (
                <></>
            )}
        </div>
    );
}
