import React from 'react';
import { deleteAsyncIntegration } from 'modules/integrations';
import EditIcon from '@material-ui/icons/Edit';
import SettingsIcon from '@material-ui/icons/Settings';
import { Switch } from '@material-ui/core';
import Button from '@material-ui/core/Button';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import PopoverSure from 'components/VirtualComponents/PopoverSure';

const IntegrationRow = ({ installedIntegrations, installedIntegration }) => {
    return (
        <TableRow key={installedIntegrations[installedIntegration].id}>
            <TableCell>{installedIntegrations[installedIntegration].config.name}</TableCell>
            <TableCell>{installedIntegrations[installedIntegration].type}</TableCell>
            <TableCell>{JSON.stringify(installedIntegrations[installedIntegration])}</TableCell>
            <TableCell>
                <div style={{ display: 'flex' }}>
                    <PopoverSure
                        variant="text"
                        onDeleteVitem={() =>
                            deleteAsyncIntegration({
                                id: installedIntegrations[installedIntegration].id,
                            })
                        }
                    />
                    <Button
                        variant="text"
                        color="secondary"
                        onClick={() => {
                            console.log('deleting');
                        }}
                    >
                        <SettingsIcon />
                    </Button>
                    <Button
                        variant="text"
                        color="secondary"
                        onClick={() => {
                            console.log('edit');
                        }}
                    >
                        <EditIcon />
                    </Button>
                    <Switch color="primary" />
                </div>
            </TableCell>
        </TableRow>
    );
};

export default IntegrationRow;
