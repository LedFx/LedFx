import React from 'react';

import Grid from '@material-ui/core/Grid';

import MelbankGraph from 'components/MelbankGraph';

class DeveloperView extends React.Component {
    render() {
        const { graphString } = this.props.match.params;

        let graphList = graphString.split('+');
        let graphDom = Object.keys(graphList).map(graphIndex => {
            return (
                <Grid item xs={12}>
                    <p>{graphList[graphIndex].replace(/^\w/, c => c.toUpperCase())} Graph</p>
                    <MelbankGraph key={graphIndex} graphId={graphList[graphIndex]} />
                </Grid>
            );
        });

        return (
            <Grid container spacing={3}>
                {graphDom}
            </Grid>
        );
    }
}

export default DeveloperView;
