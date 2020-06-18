import React from 'react';
import withStyles from '@material-ui/core/styles/withStyles';
import { connect } from 'react-redux';

import Dialog from '@material-ui/core/Dialog';
import DialogContent from '@material-ui/core/DialogContent';
import DialogTitle from '@material-ui/core/DialogTitle';
import DialogContentText from '@material-ui/core/DialogContentText';

import SchemaFormCollection from 'components/SchemaForm';
import { addDevice } from 'actions';

const styles = theme => ({
    button: {
        float: 'right',
    },
});

class PresetsConfigDialog extends React.Component {
    handleClose = () => {
        this.props.onClose();
    };

    handleSubmit = (type, config) => {
        this.props.dispatch(addDevice(type, config));
        this.props.onClose();
    };

    render() {
        const { classes, dispatch, schemas, onClose, ...otherProps } = this.props;
        return (
            <Dialog
                onClose={this.handleClose}
                className={classes.cardResponsive}
                aria-labelledby="form-dialog-title"
                {...otherProps}
            >
                <DialogTitle id="form-dialog-title">Add Preset</DialogTitle>
                <DialogContent className={classes.cardResponsive}>
                    <DialogContentText>
                        To add a preset to LedFx, please first configure the effects you wish to
                        save, select the type of preset you wish, and then provide the necessary
                        configuration.
                    </DialogContentText>
                    <SchemaFormCollection
                        schemaCollection={schemas.devices}
                        onSubmit={this.handleSubmit}
                        useAdditionalProperties={true}
                        submitText="Add"
                        onCancel={this.handleClose}
                    />
                </DialogContent>
            </Dialog>
        );
    }
}

function mapStateToProps(state) {
    const { schemas } = state;

    return {
        schemas,
    };
}

export default connect(mapStateToProps)(withStyles(styles)(PresetsConfigDialog));
