import React from 'react';
import { deleteAsyncIntegration } from 'modules/integrations';
import EditIcon from '@material-ui/icons/Edit';
import { Switch } from '@material-ui/core';
import Button from '@material-ui/core/Button';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import PopoverSure from 'components/VirtualComponents/PopoverSure';

const DataRow = ({ id, name, type, data }) =>
    data.map(dr => (
        <TableRow key={id}>
            <TableCell>{name}</TableCell>
            <TableCell>{type}</TableCell>
            <TableCell>{dr[0]}</TableCell>
            <TableCell>{dr[1] && dr[1].scene_name}</TableCell>
            <TableCell>{JSON.stringify(dr[3])}</TableCell>
            <TableCell>
                <div style={{ display: 'flex' }}>
                    <PopoverSure
                        variant="text"
                        onDeleteVitem={() =>
                            deleteAsyncIntegration({
                                id: id,
                            })
                        }
                    />
                    <Button
                        variant="text"
                        color="secondary"
                        onClick={() => {
                            // console.log('edit');
                        }}
                        //Need to do, onClick edit DialogAddEventListener.
                    >
                        <EditIcon />
                    </Button>
                    <Switch color="primary" checked={data && dr && dr[2]} />
                </div>
            </TableCell>
        </TableRow>
    ));

export default DataRow;
