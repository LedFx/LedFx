import React, { useEffect } from 'react';
import { useDispatch } from 'react-redux';
import Grid from '@material-ui/core/Grid';
import LogCard from './LogCard';
import GeneralCard from './GeneralCard';
import InfoCard from './InfoCard';
import { fetchDisplayList } from 'modules/displays';
import DevCard from './DevCard';

const AdvancedView = () => {
    const dispatch = useDispatch();

    useEffect(() => {
        dispatch(fetchDisplayList());
    }, [dispatch]);

    return (
        <Grid container spacing={2}>

            <Grid container item xs={12} sm={12} md={12} lg={4} xl={3} spacing={3}>
                <Grid item xs={12} sm={6} md={6} lg={12} >
                    <GeneralCard />
                </Grid>
                <Grid item xs={12} sm={6} md={6} lg={12}>
                    <InfoCard />
                </Grid>
            </Grid>
            <Grid item xs={12} sm={12} md={12} lg={8} xl={9}>
                <LogCard />
                {parseInt(window.localStorage.getItem('BladeMod')) > 1 && (
                    <DevCard />
                )}
            </Grid>

        </Grid>
    );
};

export default AdvancedView;
