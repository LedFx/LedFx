import React from 'react';
import Card from '@material-ui/core/Card';
import CardActions from '@material-ui/core/CardActions';
import CardContent from '@material-ui/core/CardContent';
import { makeStyles } from '@material-ui/core/styles';
import DialogAddIntegration from 'components/IntegrationComponents/DialogAddIntegration';
import Typography from '@material-ui/core/Typography';

const useStyles = makeStyles({
    integrationCard: {
        width: 300,
        height: 220,
        justifyContent: 'space-between',
        display: 'flex',
        flexDirection: 'column',
    },
    title: {
        fontSize: 14,
    },
    pos: {
        marginBottom: 12,
    },
});

const IntegrationsCard = ({ intTypes, int }) => {
    const classes = useStyles();
    return (
        <Card className={classes.integrationCard} variant="outlined">
            <CardContent>
                <Typography className={classes.title} color="textSecondary" gutterBottom>
                    Integration
                </Typography>
                <Typography variant="h5" component="h2">
                    {intTypes[int].name}
                </Typography>
                <Typography className={classes.pos} color="textSecondary">
                    v0.0.1
                </Typography>
                <Typography variant="body2" component="p">
                    {intTypes[int].description}
                </Typography>
            </CardContent>
            <CardActions>
                <DialogAddIntegration integration={intTypes[int].id} />
            </CardActions>
        </Card>
    );
};

export default IntegrationsCard;
