import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import Button from '@material-ui/core/Button';
import { Badge } from '@material-ui/core';
import {
    DialogTitle,
    DialogContent,
    DialogContentText,
    FormControlLabel,
    Checkbox,
} from '@material-ui/core';
import Dialog from '@material-ui/core/Dialog';
import { makeStyles } from '@material-ui/core/styles';
import { setConfig } from 'modules/settings';
import { setDisplay } from 'modules/displays';


const useStyles = makeStyles(theme => ({
    badgeButton: {
        height: '16px',
        fontSize: '12px',
        minWidth: 'unset',
        padding: '3px 5px',
        flexGrow: 0,
    },
}));

function SimpleDialog({ onClose, open, display }) {
    const [remember, setRemember] = React.useState(false);
    const handleDialogClose = value => {
        onClose({ display: display.id, value, save_preferred: remember });
    };

    const handleListItemClick = event => {
        setRemember(event.target.checked);

        // onClose(event);
    };

    return (
        <Dialog onClose={handleDialogClose} aria-labelledby="simple-dialog-title" open={open}>
            <DialogTitle id="simple-dialog-title">Possible Performance Improvement</DialogTitle>

            <DialogContent dividers>
                <DialogContentText>

            A WLED device with over 480 LEDs has been detected in E1.31 mode.
            DDP has less overhead and is supported by WLED.
            LedFx can switch the mode of WLED for you.
            Do you want to convert all existing WLED devices to DDP?

            You will be unable to send E1.31 to these devices without changing back to E1.31

            </DialogContentText>
                <Button
                    variant="outlined"
                    onClick={() => window.open("https://ledfx.readthedocs.io/en/master/trouble.html#id3", "_blank")}
                >Click here for more info...</Button>
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        margin: '3rem 0 1rem 0',
                    }}
                >
                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={remember}
                                onChange={handleListItemClick}
                                name="checkedB"
                                color="primary"
                            />
                        }
                        label="Set as Preferred Mode"
                    />
                    <div>
                        <Button
                            color="primary"
                            variant="contained"
                            style={{ marginRight: '1rem' }}
                            onClick={() => handleDialogClose('E131')}
                        >
                            Keep E1.31
                        </Button>
                        <Button
                            color="primary"
                            variant="contained"
                            onClick={() => handleDialogClose('DDP')}
                        >
                            Switch to DDP
                        </Button>
                    </div>
                </div>
                <div style={{ textAlign: 'right' }}></div>
            </DialogContent>
        </Dialog>
    );
}

const TypeBadge = ({ display, variant, style }) => {
    const [open, setOpen] = React.useState(false);
    const deviceList = useSelector(state => state.devices.list);
    const classes = useStyles();
    const dispatch = useDispatch();
    const handleClickOpen = () => {
        setOpen(true);
    };
    const handleClose = value => {
        if (value.save_preferred) {
            dispatch(setConfig({ config: { wled_preferred_mode: value.value } }));
        }
        dispatch(setDisplay(display.id, { config: { sync_mode: value.value } }));
        setOpen(false);
        // setSelectedValue(value);
    };
    const dev = deviceList.find(d => d.id === display.is_device);
    const type = dev && dev.type;

    return (
        <div>
            {type === 'wled' ? (
                <>
                    <Button
                        variant={variant}
                        style={{ opacity: '0.3', marginRight: '0.5rem', ...style }}
                        size="small"
                        className={classes.badgeButton}
                        onClick={handleClickOpen}
                    >
                        {`${type}` || 'VIRTUAL'}
                    </Button>

                    {dev.config.sync_mode === 'E131' ? (
                        <Badge badgeContent={'!'} color="primary">
                            <Button
                                variant={variant}
                                style={{ opacity: '0.3', ...style }}
                                size="small"
                                className={classes.badgeButton}
                                onClick={handleClickOpen}
                            >
                                {`${dev.config.sync_mode}` || ''}
                            </Button>
                        </Badge>
                    ) : (
                        <Button
                            variant={variant}
                            style={{ opacity: '0.3', ...style }}
                            size="small"
                            className={classes.badgeButton}
                            onClick={handleClickOpen}
                        >
                            {`${dev.config.sync_mode}` || ''}
                        </Button>
                    )}
                    <SimpleDialog open={open} onClose={handleClose} display={display} />
                </>
            ) : (
                <Button
                    variant={variant}
                    disabled
                    size="small"
                    className={classes.badgeButton}
                    style={{ ...style }}
                >
                    {type || 'VIRTUAL'}
                </Button>
            )}
        </div>
    );
};

export default TypeBadge;
