import React from 'react';
import { deleteQLCListener } from 'proxies/integrations';
import { getAsyncIntegrations } from 'modules/integrations';
import EditIcon from '@material-ui/icons/Edit';
import { Switch } from '@material-ui/core';
import Button from '@material-ui/core/Button';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import PopoverSure from 'components/PopoverSure';
import { useDispatch } from 'react-redux';

const DataRow = ({ id, name, type, data }) => {
    const dispatch = useDispatch();

    const [test, setTest] = React.useState(false);
    React.useEffect(() => {
        dispatch(getAsyncIntegrations());
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [test]);
    const deleteQLC = async (id, dr) => {
        await deleteQLCListener(id, {
            data: {
                event_type: dr[0],
                event_filter: { scene_name: dr[1].scene_name },
            },
        });
        //let newData = data.filter(x => x[0] !== dr[0]);
        setTest(!test);
    };
    return data
        ? data.map((dr, i) => (
              <TableRow key={i}>
                  <TableCell>{name}</TableCell>
                  <TableCell>{type}</TableCell>
                  <TableCell>{dr[0]}</TableCell>
                  <TableCell>{dr[1] && dr[1].scene_name}</TableCell>
                  <TableCell>{JSON.stringify(dr[3])}</TableCell>
                  <TableCell>
                      <div style={{ display: 'flex' }}>
                          <PopoverSure variant="text" onConfirm={() => deleteQLC(id, dr)} />
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
          ))
        : false;
};

export default DataRow;
