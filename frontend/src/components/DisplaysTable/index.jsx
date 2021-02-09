import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@material-ui/core/styles';
import Table from '@material-ui/core/Table';
import TableHead from '@material-ui/core/TableHead';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import TableBody from '@material-ui/core/TableBody';

import DisplaysTableItem from './DisplaysTableItem.jsx';
import DisplayCardItem from './DisplayCardItem.jsx';

import ViewListIcon from '@material-ui/icons/ViewList';
import ViewModuleIcon from '@material-ui/icons/ViewModule';
import ToggleButton from '@material-ui/lab/ToggleButton';
import ToggleButtonGroup from '@material-ui/lab/ToggleButtonGroup';

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

function DisplaysTable({
    onDeleteDisplay,
    classes,
    items,
    onEditDevice,
    onEditDisplay,
    deviceList,
}) {
    const [view, setView] = React.useState('list');

    const handleChange = (event, nextView) => {
        setView(nextView);
    };
    return (
        <div className={classes.tableResponsive}>
            {view === 'list' ? (
                <Table className={classes.table}>
                    <TableHead>
                        <TableRow className={classes.tableTitles}>
                            <TableCell></TableCell>
                            <TableCell>Name</TableCell>
                            <TableCell>Max Brightness</TableCell>
                            <TableCell>Crossfade</TableCell>
                            <TableCell>Center-Offset</TableCell>
                            <TableCell>Preview-Only</TableCell>
                            <TableCell align="right">
                                {/* {parseInt(window.localStorage.getItem('BladeMod')) > 2 && (
                                    <ToggleButtonGroup
                                        value={view}
                                        exclusive
                                        onChange={handleChange}
                                    >
                                        <ToggleButton value="list" aria-label="list">
                                            <ViewListIcon />
                                        </ToggleButton>
                                        <ToggleButton value="module" aria-label="module">
                                            <ViewModuleIcon />
                                        </ToggleButton>
                                    </ToggleButtonGroup>
                                )} */}
                            </TableCell>
                        </TableRow>
                    </TableHead>

                    <TableBody>
                        {items.map(display => (
                            <DisplaysTableItem
                                key={display.id}
                                display={display}
                                deviceList={deviceList}
                                onDelete={onDeleteDisplay}
                                onEditDevice={onEditDevice}
                                onEditDisplay={onEditDisplay}
                            />
                        ))}
                    </TableBody>
                </Table>
            ) : (
                <>
                    <div style={{ margin: '1rem' }} align="right">
                        <ToggleButtonGroup value={view} exclusive onChange={handleChange}>
                            <ToggleButton value="list" aria-label="list">
                                <ViewListIcon />
                            </ToggleButton>
                            <ToggleButton value="module" aria-label="module">
                                <ViewModuleIcon />
                            </ToggleButton>
                        </ToggleButtonGroup>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap' }}>
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
                </>
            )}
        </div>
    );
}

DisplaysTable.propTypes = {
    classes: PropTypes.object.isRequired,
    items: PropTypes.array.isRequired,
};

export default withStyles(styles)(DisplaysTable);
