import React from 'react';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import {
    Card,
    CardContent,
    Divider,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Typography,
    Grid,
} from '@material-ui/core';
import DeleteForeverIcon from '@material-ui/icons/DeleteForever';
import { deleteSpotifyTrigger } from 'proxies/integrations';
import { ToastContainer, toast } from 'react-toastify';
// import { getScenes } from 'modules/scenes';
// import { useEffect } from 'react';

const styles = theme => ({});

const triggersNew = [];

class TriggerList extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            triggers: triggersNew,
        };
    }

    componentDidMount() {
        console.log('Get Here', triggersNew);
        console.log(this.props.spotify);
        this.props.spotify.map(scene => {
            let sceneName = scene.name;
            let sceneId = scene.id;
            Object.keys(scene).map(function (key, index) {
                if (scene[key].constructor === Array) {
                    // console.log(scene[key]);
                    triggersNew.push({
                        trigger_id: scene[key][0] + '-' + scene[key][2],
                        songId: scene[key][0],
                        songName: scene[key][1],
                        position: scene[key][2],
                        sceneId: sceneId,
                        sceneName: sceneName,
                    });
                }
                return true;
            });
            this.setState({ triggers: triggersNew });
            return true;
        });
        // console.log(triggers);
    }

    getTime(duration) {
        return new Date(duration * 1000).toISOString().substr(11, 8);
    }

    componentDidUpdate(prevProps, prevState) {
        if (this.props.integrations !== prevProps.integrations) {
            triggersNew.length = 0;
            let temp = this.props.integrations.data;
            Object.keys(temp).map(function (key, index) {
                let temp1 = temp[key];
                let sceneName = temp1.name;
                let sceneId = temp1.name;
                Object.keys(temp1).map(function (key, index) {
                    if (temp1[key].constructor === Array) {
                        // console.log(scene[key]);
                        triggersNew.push({
                            trigger_id: temp1[key][0] + '-' + temp1[key][2],
                            songId: temp1[key][0],
                            songName: temp1[key][1],
                            position: temp1[key][2],
                            sceneId: sceneId,
                            sceneName: sceneName,
                        });
                    }
                    return true;
                });
                return true;
            });
            this.setState({ triggers: triggersNew });
        }
    }

    render() {
        // const {} = this.props;
        return (
            <Card>
                <ToastContainer />
                <CardContent>
                    {this.state.triggers.length > 0 ? (
                        <List>
                            <ListItem>
                                <Grid container>
                                    <Grid item xs={6}>
                                        <ListItemText primary="Song" secondary="Position" />
                                    </Grid>
                                    <Grid item xs={5}>
                                        <ListItemText
                                            primary="Scene Name"
                                            secondary="Scene Selected"
                                        />
                                    </Grid>
                                    <Grid item xs={1}></Grid>
                                </Grid>
                            </ListItem>
                            {this.state.triggers.map((trigger, i) => (
                                <div key={i}>
                                    <ListItem>
                                        <Grid container>
                                            <Grid item xs={6}>
                                                <ListItemText
                                                    primary={trigger.songName}
                                                    secondary={this.getTime(trigger.position)}
                                                />
                                            </Grid>
                                            <Grid item xs={5}>
                                                <ListItemText primary={trigger.sceneName} />
                                            </Grid>
                                            <Grid item xs={1}>
                                                <ListItemIcon>
                                                    <DeleteForeverIcon
                                                        color="error"
                                                        onClick={() => {
                                                            deleteSpotifyTrigger('spotify', {
                                                                data: {
                                                                    trigger_id: trigger.trigger_id,
                                                                },
                                                            });
                                                            toast.error('Trigger deleted');
                                                            this.setState({
                                                                triggers:
                                                                    this.state.triggers.filter(
                                                                        x =>
                                                                            x.trigger_id !==
                                                                            trigger.trigger_id
                                                                    ),
                                                            });
                                                        }}
                                                        style={{ cursor: 'pointer' }}
                                                    />
                                                </ListItemIcon>
                                            </Grid>
                                        </Grid>
                                    </ListItem>
                                    <Divider />
                                </div>
                            ))}
                        </List>
                    ) : (
                        <Typography>Add Some Triggers To View Them Here</Typography>
                    )}
                </CardContent>
            </Card>
        );
    }
}

export default connect(
    state => ({
        spotify: state.scenes.list,
        integrations: state.integrations.list.spotify,
    }),
    {}
)(withStyles(styles)(TriggerList));
