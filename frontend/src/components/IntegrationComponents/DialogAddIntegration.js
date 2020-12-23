import React from 'react';
import PropTypes from 'prop-types';
import { makeStyles } from '@material-ui/core/styles';
import Button from '@material-ui/core/Button';
import DialogTitle from '@material-ui/core/DialogTitle';
import DialogContent from '@material-ui/core/DialogContent';
import DialogActions from '@material-ui/core/DialogActions';
import Dialog from '@material-ui/core/Dialog';
import AddCircleIcon from '@material-ui/icons/AddCircle';
import { useSelector } from 'react-redux';
import { SchemaForm, utils } from 'react-schema-form';
import * as integrationsProxies from 'proxies/integrations';

function ConfirmationDialogRaw(props) {
    const { onClose, value: valueProp, open, ...other } = props;
    const [value, setValue] = React.useState(valueProp);
    const radioGroupRef = React.useRef(null);
    const integrationTypes = useSelector(state => state.schemas.integrationTypes || {});
    const integration = props.integration;
    const [model] = React.useState({});
    // console.log('YZ2', integration, integrationTypes, ' ==> ', integrationTypes[integration]);
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
        integrationsProxies.createIntegration({ config: model, type: 'qlc' });
    };

    // const handleChange = event => {
    //     // setValue(event.target.value);
    // };
    const onModelChange = (key, val) => {
        utils.selectOrSet(key, model, val);

        // setModel(val);
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
            <DialogTitle id="confirmation-dialog-title">
                {integrationTypes[integration].name} Integration Setup
            </DialogTitle>
            <DialogContent dividers>
                <SchemaForm
                    // className={classes.schemaForm}
                    schema={{
                        type: 'object',
                        title: 'Configuration',
                        properties: {},
                        ...(integrationTypes ? integrationTypes[integration].schema : {}),
                    }}
                    form={
                        integrationTypes[integration] &&
                        integrationTypes[integration].schema.required
                    }
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

export default function ConfirmationDialog({ virtual, deviceList, config, integration }) {
    const classes = useStyles();
    const [open, setOpen] = React.useState(false);

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
                    aria-haspopup="true"
                    onClick={handleClickListItem}
                    role="listitem"
                >
                    ADD
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
