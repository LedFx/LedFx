import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@material-ui/core/styles';
import DisplayCardItem from './DisplayCardItem.jsx';

import DisplayCardItemPortrait from './DisplayCardItemPortrait.jsx';

const styles = theme => ({
    table: {
        borderSpacing: '0',
        borderCollapse: 'collapse',
    },
    tableTitles: {
        '@media (max-width: 1200px)': {
            display: 'none',
        },
    },
    tableResponsive: {
        overflowX: 'auto',
    },
});

const DisplayCards = ({
    onDeleteDisplay,
    classes,
    items,
    onEditDevice,
    onEditDisplay,
    deviceList,
    view,
}) =>
    view === 'cards' ? (
        <div
            style={{
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'flex-start',
                margin: '-0.5rem',
            }}
        >
            {items.map(display => (
                <DisplayCardItem
                    key={display.id}
                    display={display}
                    deviceList={deviceList}
                    onDelete={onDeleteDisplay}
                    onEditDevice={onEditDevice}
                    onEditDisplay={onEditDisplay}
                />
            ))}
        </div>
    ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', margin: '-0.5rem' }}>
            {items.map(display => (
                <DisplayCardItemPortrait
                    key={display.id}
                    display={display}
                    deviceList={deviceList}
                    onDelete={onDeleteDisplay}
                    onEditDevice={onEditDevice}
                    onEditDisplay={onEditDisplay}
                />
            ))}
        </div>
    );

DisplayCards.propTypes = {
    classes: PropTypes.object.isRequired,
    items: PropTypes.array.isRequired,
};

export default withStyles(styles)(DisplayCards);
