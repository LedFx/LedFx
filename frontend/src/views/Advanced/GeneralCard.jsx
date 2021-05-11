import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import { FormControl, Button, Divider } from '@material-ui/core';
import Select from '@material-ui/core/Select';
import CloudUploadIcon from '@material-ui/icons/CloudUpload';
import CloudDownloadIcon from '@material-ui/icons/CloudDownload';
import PowerSettingsNewIcon from '@material-ui/icons/PowerSettingsNew';
import AudioInputCard from './AudioInput'
import { getAudioInputs, setAudioInput } from 'modules/settings';
import { Delete, Refresh } from '@material-ui/icons';
import * as settingProxies from 'proxies/settings';
import { showdynSnackbar } from 'modules/ui';
const useStyles = makeStyles({
    content: {
        display: 'flex',
        flexDirection: 'column',
    },
});

const GeneralCard = () => {

    const dispatch = useDispatch();
    const classes = useStyles();
    const [theme, setTheme] = useState(window.localStorage.getItem('blade') || 0);
    const settings = useSelector(state => state.settings)
    const { audioInputs } = settings;
    function download(content, fileName, contentType) {
        var a = document.createElement("a");
        var file = new Blob([JSON.stringify(content, null, 4)], { type: contentType });
        a.href = URL.createObjectURL(file);
        a.download = fileName;
        a.click();
    }

    const shutdown = async () => {
        try {
            const response = await settingProxies.shutdown();
            if (response.statusText !== 'OK') {
                showdynSnackbar({ message: 'Error while shutting down LedFx ...', type: 'error' })
                throw new Error('Error...');
            }
            dispatch(
                showdynSnackbar({ message: 'Shutting down LedFx ...', type: 'info' })
            );
        } catch (error) {
            console.log(error)
            showdynSnackbar({ message: 'Error while shutting down LedFx ...', type: 'error' })
        }
    }
    const configDownload = async () => {
        try {
            const response = await settingProxies.getSystemConfig();
            if (response.statusText !== 'OK') {
                dispatch(
                    showdynSnackbar({ message: 'Error while downloading config.json', type: 'error' })
                )
                throw new Error('Error fetching system config');
            }
            download(response.data.config, 'config.json', 'application/json');
            dispatch(
                showdynSnackbar({ message: 'downloading config.json', type: 'info' })
            )
        } catch (error) {
            console.log(error)
            dispatch(
                showdynSnackbar({ message: 'Error while downloading config.json', type: 'error' })
            )
        }
    }
    const configDelete = async () => {
        try {
            const response = await settingProxies.deleteSystemConfig();
            if (response.statusText !== 'OK') {
                dispatch(
                    showdynSnackbar({ message: 'Error while downloading config.json', type: 'error' })
                )
                throw new Error('Error fetching system config');
            }
            // download(response.data.config, 'config.json', 'application/json');
            // dispatch(
            //     showdynSnackbar({ message: 'downloading config.json', type: 'info' })
            // )
        } catch (error) {
            console.log(error)
            dispatch(
                showdynSnackbar({ message: 'Error while downloading config.json', type: 'error' })
            )
        }
    }
    const changeTheme = event => {
        setTheme(event.target.value);
        window.localStorage.setItem('blade', event.target.value);
        window.location = window.location.href;
    };
    // const onChangePreferredMode = value => {
    //     dispatch(setConfig({ config: { wled_preferences: { wled_preferred_mode: { preferred_mode: value, user_enabled: true } } } }));
    // };
    // const onChangeStartupScan = value => {
    //     dispatch(setConfig({ config: { scan_on_startup: value } }));
    // };

    useEffect(() => {
        dispatch(getAudioInputs())
    }, [dispatch])
    return (
        <Card style={{ marginBottom: '2rem' }}>
            <CardHeader title="General" subheader="Configure LedFx-Settings" />
            <CardContent className={classes.content}>
                {/* <FormControlLabel
                    control={
                        <Checkbox
                            name="scanAtStartup"
                        />
                    }
                    label="Scan for WLED on startup"
                />
                <FormControlLabel
                    value="scan"
                    control={<Switch color="primary" />}
                    label="Scan for WLED on startup"
                    labelPlacement="end"
                /> */}
                <AudioInputCard raw {...audioInputs} onChange={(e) => dispatch(setAudioInput(e))} />
                {/* <FormControl>
                    <InputLabel id="wled-scan-selector">Scan for WLED on startup</InputLabel>
                    <Select
                        labelId="wled-scan-selector"
                        id="wled-scan-select"
                        value={settings.scan_on_startup}
                        onChange={(e) => onChangeStartupScan(e.target.value)}
                    >
                        <MenuItem value={true}>Yes</MenuItem>
                        <MenuItem value={false}>No</MenuItem>
                    </Select>

                </FormControl>
                <FormControl>
                    <InputLabel id="wled-mode-selector">Preferred WLED mode</InputLabel>
                    <Select
                        labelId="wled-mode-selector"
                        id="wled-mode-select"
                        value={settings.wled_preferred_mode}
                        onChange={(e) => onChangePreferredMode(e.target.value)}
                    >
                        <MenuItem value={"unset"}>Unset</MenuItem>
                        <MenuItem value={"E131"}>E131</MenuItem>
                        <MenuItem value={"DDP"}>DDP</MenuItem>
                    </Select>
                </FormControl> */}
                <FormControl>
                    <InputLabel id="theme-selector">Theme</InputLabel>
                    <Select
                        labelId="theme-selector"
                        id="theme-select"
                        value={theme}
                        onChange={changeTheme}
                    >
                        <MenuItem value={0}>Original</MenuItem>
                        <MenuItem value={1}>OriginalDark</MenuItem>
                        <MenuItem value={2}>BladeLight</MenuItem>
                        <MenuItem value={3}>BladeDark</MenuItem>
                        <MenuItem value={4}>GreenLight</MenuItem>
                        <MenuItem value={5}>GreenDark</MenuItem>
                        <MenuItem value={6}>BlueLight</MenuItem>
                        <MenuItem value={7}>BlueDark</MenuItem>
                    </Select>
                </FormControl>
                <Divider style={{ margin: '1rem 0' }} />
                <Button
                    size="small"
                    startIcon={<CloudUploadIcon />}
                    variant="outlined"
                    style={{ marginTop: '1.5rem' }}
                    onClick={configDownload}
                >
                    Export Config
                </Button>
                <Button
                    size="small"
                    startIcon={<Delete />}
                    variant="outlined"
                    style={{ marginTop: '0.5rem' }}
                    onClick={configDelete}

                >
                    Reset Config
                </Button>

                {parseInt(window.localStorage.getItem('BladeMod')) > 1 && (
                    <>
                        <Button
                            size="small"
                            startIcon={<CloudDownloadIcon />}
                            variant="outlined"
                            style={{ marginTop: '0.5rem' }}

                        >
                            Import Config
                            <input
                                type="file"
                                hidden
                            />
                        </Button>
                        <Button
                            size="small"
                            startIcon={<Refresh />}
                            variant="outlined"
                            style={{ marginTop: '0.5rem' }}
                            disabled
                        >
                            Check Updates
                        </Button>
                    </>
                )}
                <Button
                    size="small"
                    startIcon={<PowerSettingsNewIcon />}
                    variant="outlined"
                    style={{ marginTop: '0.5rem' }}
                    onClick={shutdown}
                >
                    Shutdown
                </Button>

            </CardContent>
        </Card>
    );
};

export default GeneralCard;
