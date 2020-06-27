import React from 'react';
import PropTypes from 'prop-types';
import withStyles from '@material-ui/core/styles/withStyles';
import Typography from '@material-ui/core/Typography';

import SchemaFormCollection from 'components/SchemaForm';

const styles = theme => ({});

class EffectControl extends React.Component {
    handleClearEffect = () => {
        const { onClear } = this.props;
        onClear(this.props.device.id);
    };

    handleSetEffect = (type, config) => {
        const { onSubmit, device } = this.props;
        onSubmit({ deviceId: device.id, type, config });
    };

    render() {
        const { schemas, effect } = this.props;

        if (schemas.effects) {
            return (
                <>
                    <Typography variant="h5" color="inherit">
                        Effect Control
                    </Typography>
                    <SchemaFormCollection
                        schemaCollection={schemas.effects}
                        selectedType={effect?.type}
                        initial={effect?.config}
                        onSubmit={this.handleSetEffect}
                        onCancel={this.handleClearEffect}
                        cancelText="Clear Effect"
                        submitText="Set Effect"
                    />
                </>
            );
        }

        return <p>Loading</p>;
    }
}

EffectControl.propTypes = {
    classes: PropTypes.object.isRequired,
    schemas: PropTypes.object.isRequired,
    device: PropTypes.object.isRequired,
    effect: PropTypes.object.isRequired,
};

export default withStyles(styles)(EffectControl);
