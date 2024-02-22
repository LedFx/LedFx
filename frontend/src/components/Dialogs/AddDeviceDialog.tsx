/* eslint-disable prettier/prettier */
/* eslint-disable @typescript-eslint/indent */
/* eslint-disable no-restricted-syntax */
/* eslint-disable guard-for-in */
/* eslint-disable no-unused-expressions */
import { useState, useEffect } from 'react';
import { styled } from '@mui/material/styles';
import {
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Select,
  MenuItem,
  Button,
  Divider,
} from '@mui/material';
import useStore from '../../store/useStore';
import SchemaForm from '../SchemaForm/SchemaForm/SchemaForm';

const PREFIX = 'AddDeviceDialog';

const classes = {
  wrapper: `${PREFIX}-wrapper`
};

const StyledDialog = styled(Dialog)((
  {
    theme
  }
) => ({
  [`& .${classes.wrapper}`]: {
    minWidth: '200px',
    padding: '16px 1.2rem 6px 1.2rem',
    border: '1px solid #999',
    borderRadius: '10px',
    position: 'relative',
    margin: '1rem 0',
    display: 'flex',
    alignItems: 'center',
    '@media (max-width: 580px)': {
      width: '100%',
      margin: '0.5rem 0',
    },
    '& > label': {
      top: '-0.7rem',
      display: 'flex',
      alignItems: 'center',
      left: '1rem',
      padding: '0 0.3rem',
      position: 'absolute',
      fontVariant: 'all-small-caps',
      fontSize: '0.9rem',
      letterSpacing: '0.1rem',
      backgroundColor: theme.palette.background.paper,
      boxSizing: 'border-box',
    },
  }
}));

const AddDeviceDialog = () => {


  const getDevices = useStore((state) => state.getDevices);
  const getVirtuals = useStore((state) => state.getVirtuals);
  const addDevice = useStore((state) => state.addDevice);
  const updateDevice = useStore((state) => state.updateDevice);
  const setAddWled = useStore((state) => state.setAddWLed);
  const devices = useStore((state) => state.devices);
  const open = useStore((state) => state.dialogs.addDevice?.open || false);
  const deviceId = useStore((state) => state.dialogs.addDevice?.edit || false);
  const initial = devices[deviceId] || { type: '', config: {} };

  const setDialogOpenAddDevice = useStore(
    (state) => state.setDialogOpenAddDevice
  );

  const deviceTypes = useStore((state) => state.schemas?.devices);
  const showSnackbar = useStore((state) => state.ui.showSnackbar);
  const [deviceType, setDeviceType] = useState('');
  const [model, setModel] = useState<any>({});

  const currentSchema = deviceType ? deviceTypes[deviceType].schema : {};

  const handleClose = () => {
    setDialogOpenAddDevice(false);
  };
  const handleAddDevice = () => {
    const cleanedModel = Object.fromEntries(
      Object.entries(model).filter(([_, v]) => v !== '')
    );
    const defaultModel = {} as any;

    for (const key in currentSchema.properties) {
      currentSchema.properties[key].default !== undefined
        ? (defaultModel[key] = currentSchema.properties[key].default)
        : undefined;
    }

    const valid = currentSchema.required.every((val: string) =>
      Object.keys({ ...defaultModel, ...cleanedModel }).includes(val)
    );

    if (!valid) {
      showSnackbar('warning', 'Please fill in all required fields.');
    } else if (
      initial.config &&
      Object.keys(initial.config).length === 0 &&
      initial.config?.constructor === Object
    ) {
      addDevice({
        type: deviceType,
        config: { ...defaultModel, ...cleanedModel },
      }).then((res: any) => {
        if (res !== 'failed') {
          if (deviceType === 'wled') {
            const deviceIps = Object.values(devices).map((device: any) => device.config.ip_address)
            const newDevices = [] as { name: string, ip_address: string}[]
            res.nodes && res.nodes.forEach((node: any) => {
              if (node.ip && !deviceIps.includes(node.ip)) {
                newDevices.push({ name: node.name, ip_address: node.ip})
              }
            })
            if (newDevices.length > 0) {
              setAddWled(newDevices)
            }
          }
          setDialogOpenAddDevice(false);
          getDevices();
          getVirtuals();
        }
      });
    } else {
      // console.log("EDITING");
      updateDevice(deviceId, { config: model }).then((res) => {
        if (res !== 'failed') {
          setDialogOpenAddDevice(false);
          getDevices();
          getVirtuals();
        }
      });
    }
  };
  const handleTypeChange = (value: string, init = {}) => {
    setDeviceType(value);
    setModel(init);
  };
  const handleModelChange = (config: any) => {
    setModel({ ...model, ...config });
  };

  function filterObject(obj: any, callback: any) {
    return Object.fromEntries(Object.entries(obj).
      filter(([key, val]) => callback(key, val)));
  }
  useEffect(() => {
    handleTypeChange(initial.type, initial.config);
  }, [initial.type]);

  return (
    <StyledDialog
      open={open}
      onClose={handleClose}
      aria-labelledby="form-dialog-title"
    >
      <DialogTitle id="form-dialog-title">
        {initial.config &&
        Object.keys(initial.config).length === 0 &&
        initial.config?.constructor === Object
          ? `Add ${deviceType.toUpperCase()} Device`
          : `${deviceType.toUpperCase()} Config`}
      </DialogTitle>
      <DialogContent>
        <DialogContentText>
          To add a device to LedFx, please first select the type of device you
          wish to add then provide the necessary configuration.
        </DialogContentText>
        <div className={classes.wrapper}>
          <label>Device Type</label>
          <Select
            label="Type"
            disabled={
              !(
                initial.config &&
                Object.keys(initial.config).length === 0 &&
                initial.config?.constructor === Object
              )
            }
            style={{ flexGrow: 1 }}
            value={deviceType}
            onChange={(e: any) => handleTypeChange(e.target.value)}
          >
            {deviceTypes &&
              Object.keys(deviceTypes).map((item, i) => (
                <MenuItem key={i} value={item}>
                  {item}
                </MenuItem>
              ))}
          </Select>
        </div>
        <Divider style={{ marginBottom: '1rem' }} />
        {model && (
          <SchemaForm
            type={deviceType}
            schema={initial.config &&
              Object.keys(initial.config).length === 0 &&
              initial.config?.constructor === Object
                ? currentSchema
                : { ...currentSchema, properties: currentSchema.properties && Object.keys(currentSchema.properties).filter(p => p !== 'icon_name' && p !== 'name')
                  .reduce((cur, key) => Object.assign(cur, { [key]: currentSchema.properties[key] }), {})
                }}
            model={initial.config &&
              Object.keys(initial.config).length === 0 &&
              initial.config?.constructor === Object
                ? model
                : filterObject(model, (p:string,_v: any) => p !== 'icon_name' && p !== 'name')}
            onModelChange={handleModelChange}
            hideToggle={!deviceType}
          />
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} color="primary">
          Cancel
        </Button>
        <Button onClick={handleAddDevice} color="primary">
          {initial.config &&
          Object.keys(initial.config).length === 0 &&
          initial.config?.constructor === Object
            ? 'Add'
            : 'Save'}
        </Button>
      </DialogActions>
    </StyledDialog>
  );
};

export default AddDeviceDialog;
