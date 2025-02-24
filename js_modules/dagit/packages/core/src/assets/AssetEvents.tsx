import {gql, useQuery} from '@apollo/client';
import {
  Box,
  ButtonGroup,
  ColorsWIP,
  NonIdealState,
  Spinner,
  Caption,
  Subheading,
  Warning,
  Checkbox,
} from '@dagster-io/ui';
import flatMap from 'lodash/flatMap';
import uniq from 'lodash/uniq';
import qs from 'qs';
import * as React from 'react';
import {Link} from 'react-router-dom';

import {useStateWithStorage} from '../hooks/useStateWithStorage';
import {METADATA_ENTRY_FRAGMENT} from '../metadata/MetadataEntry';
import {SidebarSection} from '../pipelines/SidebarComponents';
import {titleForRun} from '../runs/RunUtils';
import {RepositorySelector} from '../types/globalTypes';
import {CurrentRunsBanner} from '../workspace/asset-graph/CurrentRunsBanner';
import {LiveDataForNode} from '../workspace/asset-graph/Utils';

import {AssetEventsTable} from './AssetEventsTable';
import {ASSET_LINEAGE_FRAGMENT} from './AssetLineageElements';
import {AssetValueGraph, AssetValueGraphData} from './AssetValueGraph';
import {AssetViewParams} from './AssetView';
import {LatestMaterializationMetadata} from './LastMaterializationMetadata';
import {AssetEventGroup, groupByPartition} from './groupByPartition';
import {AssetKey} from './types';
import {AssetEventsQuery, AssetEventsQueryVariables} from './types/AssetEventsQuery';
import {
  LastRunQuery,
  LastRunQueryVariables,
  LastRunQuery_repositoryOrError_Repository_latestRunByStep_JobRunsCount,
  LastRunQuery_repositoryOrError_Repository_latestRunByStep_LatestRun,
} from './types/LastRunQuery';

interface Props {
  assetKey: AssetKey;
  asSidebarSection?: boolean;
  liveData?: LiveDataForNode;
  params: AssetViewParams;
  paramsTimeWindowOnly: boolean;
  setParams: (params: AssetViewParams) => void;

  // This timestamp is a "hint", when it changes this component will refetch
  // to retrieve new data. Just don't want to poll the entire table query.
  assetLastMaterializedAt: string | undefined;

  // This is passed in because we need to know whether to default to partition
  // grouping /before/ loading all the data.
  assetHasDefinedPartitions: boolean;
  repository?: RepositorySelector;
  opName?: string | null;
}

/**
 * If the asset has a defined partition space, we load all materializations in the
 * last 100 partitions. This ensures that if you run a huge backfill of old partitions,
 * you still see accurate info for the last 100 partitions in the UI. A count-based
 * limit could cause random partitions to disappear if materializations were out of order.
 */
function useRecentAssetEvents(
  assetKey: AssetKey,
  assetHasDefinedPartitions: boolean,
  xAxis: 'partition' | 'time',
  before?: string,
) {
  const loadUsingPartitionKeys = assetHasDefinedPartitions && xAxis === 'partition';

  const {data, loading, refetch} = useQuery<AssetEventsQuery, AssetEventsQueryVariables>(
    ASSET_EVENTS_QUERY,
    {
      variables: loadUsingPartitionKeys
        ? {
            assetKey: {path: assetKey.path},
            before: before,
            partitionInLast: 120,
          }
        : {
            assetKey: {path: assetKey.path},
            before: before,
            limit: 100,
          },
    },
  );

  return React.useMemo(() => {
    const asset = data?.assetOrError.__typename === 'Asset' ? data?.assetOrError : null;
    const materializations = asset?.assetMaterializations || [];
    const observations = asset?.assetObservations || [];

    const allPartitionKeys = asset?.definition?.partitionKeys;
    const loadedPartitionKeys =
      loadUsingPartitionKeys && allPartitionKeys
        ? allPartitionKeys.slice(allPartitionKeys.length - 120)
        : undefined;

    return {asset, loadedPartitionKeys, materializations, observations, loading, refetch};
  }, [data, loading, refetch, loadUsingPartitionKeys]);
}

function useRecentRunWarnings(
  opName: string | null | undefined,
  grouped: AssetEventGroup[],
  repositorySelector?: RepositorySelector,
) {
  const {data} = useQuery<LastRunQuery, LastRunQueryVariables>(LAST_RUNS_QUERY, {
    skip: !repositorySelector,
    pollInterval: 15 * 1000,
    variables: {
      repositorySelector: repositorySelector!,
    },
  });
  return React.useMemo(() => {
    const lastRunInfo =
      data?.repositoryOrError.__typename === 'Repository' &&
      data.repositoryOrError.latestRunByStep.length > 0
        ? data.repositoryOrError
        : null;
    const latestRuns: LastRunQuery_repositoryOrError_Repository_latestRunByStep_LatestRun[] = [];
    const jobRunsCounts: LastRunQuery_repositoryOrError_Repository_latestRunByStep_JobRunsCount[] = [];
    for (const item of lastRunInfo?.latestRunByStep || []) {
      if (item.__typename === 'LatestRun') {
        latestRuns.push(item);
      } else if (item.__typename === 'JobRunsCount') {
        jobRunsCounts.push(item);
      }
    }

    const assetName = opName;
    const jobRunsThatDidntMaterializeAsset = jobRunsCounts.find((jrc) => jrc.stepKey === assetName);
    const latestRunForStepKey = latestRuns.find((lr) => lr.stepKey === assetName)?.run;

    const runWhichFailedToMaterialize =
      !jobRunsThatDidntMaterializeAsset &&
      latestRunForStepKey &&
      latestRunForStepKey.status === 'FAILURE' &&
      (!grouped.length || grouped[0].latest?.runId !== latestRunForStepKey?.id)
        ? latestRunForStepKey
        : undefined;

    return {jobRunsThatDidntMaterializeAsset, runWhichFailedToMaterialize};
  }, [data, grouped, opName]);
}

export const AssetEvents: React.FC<Props> = ({
  assetKey,
  assetLastMaterializedAt,
  assetHasDefinedPartitions,
  asSidebarSection,
  params,
  setParams,
  liveData,
  repository,
  opName,
}) => {
  const before = params.asOf ? `${Number(params.asOf) + 1}` : undefined;
  const xAxisDefault = assetHasDefinedPartitions ? 'partition' : 'time';
  const xAxis =
    assetHasDefinedPartitions && params.partition !== undefined
      ? 'partition'
      : params.time !== undefined || before
      ? 'time'
      : xAxisDefault;

  const {
    materializations,
    observations,
    loadedPartitionKeys,
    loading,
    refetch,
  } = useRecentAssetEvents(assetKey, assetHasDefinedPartitions, xAxis, before);

  React.useEffect(() => {
    if (params.asOf) {
      return;
    }
    refetch();
  }, [params.asOf, assetLastMaterializedAt, refetch]);

  const grouped = React.useMemo<AssetEventGroup[]>(() => {
    const events = [...materializations, ...observations].sort(
      (b, a) => Number(a.timestamp) - Number(b.timestamp),
    );
    if (xAxis === 'partition' && loadedPartitionKeys) {
      return groupByPartition(events, loadedPartitionKeys);
    } else {
      // return a group for every materialization to achieve un-grouped rendering
      return events.map((event) => ({
        latest: event,
        partition: event.partition || undefined,
        timestamp: event.timestamp,
        all: [],
      }));
    }
  }, [loadedPartitionKeys, materializations, observations, xAxis]);

  const {jobRunsThatDidntMaterializeAsset, runWhichFailedToMaterialize} = useRecentRunWarnings(
    opName,
    grouped,
    repository,
  );

  const activeItems = React.useMemo(() => new Set([xAxis]), [xAxis]);

  const onSetFocused = (group: AssetEventGroup) => {
    const updates: Partial<AssetViewParams> =
      xAxis === 'time'
        ? {time: group.timestamp !== params.time ? group.timestamp : ''}
        : {partition: group.partition !== params.partition ? group.partition : ''};
    setParams({...params, ...updates});
  };

  if (process.env.NODE_ENV === 'test') {
    return <span />; // chartjs and our useViewport hook don't play nicely with jest
  }

  if (asSidebarSection) {
    const latest = materializations[0];

    if (loading) {
      return (
        <Box padding={{vertical: 20}}>
          <Spinner purpose="section" />
        </Box>
      );
    }
    return (
      <>
        <CurrentRunsBanner liveData={liveData} />
        <SidebarSection title="Materialization in Last Run">
          {latest ? (
            <div style={{margin: -1, maxWidth: '100%', overflowX: 'auto'}}>
              <LatestMaterializationMetadata latest={latest} />
            </div>
          ) : (
            <Box
              margin={{horizontal: 24, bottom: 24, top: 12}}
              style={{color: ColorsWIP.Gray500, fontSize: '0.8rem'}}
            >
              No materializations found
            </Box>
          )}
        </SidebarSection>
        <SidebarSection title="Metadata Plots">
          <AssetMaterializationGraphs xAxis={xAxis} asSidebarSection groups={grouped} />
        </SidebarSection>
      </>
    );
  }

  const focused =
    grouped.find((b) =>
      params.time
        ? Number(b.timestamp) <= Number(params.time)
        : params.partition
        ? b.partition === params.partition
        : false,
    ) ||
    grouped[0] ||
    null;

  if (loading) {
    return (
      <Box style={{display: 'flex'}}>
        <Box style={{flex: 1}}>
          <Box
            flex={{justifyContent: 'space-between', alignItems: 'center'}}
            padding={{vertical: 16, horizontal: 24}}
            style={{marginBottom: -1}}
          >
            <Subheading>Asset Events</Subheading>
          </Box>
          <Box padding={{vertical: 20}}>
            <Spinner purpose="section" />
          </Box>
        </Box>
        <Box
          style={{width: '40%'}}
          border={{side: 'left', color: ColorsWIP.KeylineGray, width: 1}}
        ></Box>
      </Box>
    );
  }

  return (
    <Box style={{display: 'flex'}}>
      <Box style={{flex: 1}}>
        <Box
          flex={{justifyContent: 'space-between', alignItems: 'center'}}
          padding={{vertical: 16, horizontal: 24}}
          style={{marginBottom: -1}}
        >
          <Subheading>Asset Events</Subheading>
          {assetHasDefinedPartitions ? (
            <div style={{margin: '-6px 0 '}}>
              <ButtonGroup
                activeItems={activeItems}
                buttons={[
                  {id: 'partition', label: 'By partition'},
                  {id: 'time', label: 'By timestamp'},
                ]}
                onClick={(id: string) =>
                  setParams(
                    id === 'time'
                      ? {...params, partition: undefined, time: focused.timestamp || ''}
                      : {...params, partition: focused.partition || '', time: undefined},
                  )
                }
              />
            </div>
          ) : null}
        </Box>
        {!!jobRunsThatDidntMaterializeAsset && (
          <Warning>
            <span>
              {jobRunsThatDidntMaterializeAsset.jobNames.length > 1
                ? `${jobRunsThatDidntMaterializeAsset.jobNames.slice(0, -1).join(', ')} and ${
                    jobRunsThatDidntMaterializeAsset.jobNames.slice(-1)[0]
                  }`
                : jobRunsThatDidntMaterializeAsset.jobNames[0]}{' '}
              ran{' '}
              <Link
                to={`/instance/runs?${
                  jobRunsThatDidntMaterializeAsset.jobNames.length > 1
                    ? ''
                    : qs.stringify({
                        'q[]': `job:${jobRunsThatDidntMaterializeAsset.jobNames[0]}`,
                      })
                }`}
              >
                {jobRunsThatDidntMaterializeAsset.count} times
              </Link>{' '}
              but did not materialize this asset
            </span>
          </Warning>
        )}
        {!!runWhichFailedToMaterialize && (
          <Warning errorBackground>
            <span>
              Run{' '}
              <Link to={`/instance/runs/${runWhichFailedToMaterialize.id}`}>
                {titleForRun({runId: runWhichFailedToMaterialize.id})}
              </Link>{' '}
              failed to materialize this asset
            </span>
          </Warning>
        )}
        <CurrentRunsBanner liveData={liveData} />
        {grouped.length > 0 ? (
          <AssetEventsTable
            hasPartitions={assetHasDefinedPartitions}
            hasLineage={materializations.some((m) => m.assetLineage.length > 0)}
            groups={grouped}
            focused={focused}
            setFocused={onSetFocused}
          />
        ) : (
          <Box
            padding={{vertical: 20}}
            border={{side: 'top', color: ColorsWIP.KeylineGray, width: 1}}
          >
            <NonIdealState
              icon="asset"
              title="No materializations"
              description="No materializations were found for this asset."
            />
          </Box>
        )}
        {loadedPartitionKeys && (
          <Box padding={{vertical: 16, horizontal: 24}} style={{color: ColorsWIP.Gray400}}>
            Showing materializations for the last {loadedPartitionKeys.length} partitions.
          </Box>
        )}
      </Box>
      <Box style={{width: '40%'}} border={{side: 'left', color: ColorsWIP.KeylineGray, width: 1}}>
        <AssetMaterializationGraphs
          xAxis={xAxis}
          asSidebarSection={asSidebarSection}
          groups={grouped}
        />
      </Box>
    </Box>
  );
};

const validateHiddenGraphsState = (json: string[]) => (Array.isArray(json) ? json : []);

const AssetMaterializationGraphs: React.FC<{
  groups: AssetEventGroup[];
  xAxis: 'partition' | 'time';
  asSidebarSection?: boolean;
}> = (props) => {
  const [xHover, setXHover] = React.useState<string | number | null>(null);

  const reversed = React.useMemo(() => {
    return [...props.groups].reverse();
  }, [props.groups]);

  const graphDataByMetadataLabel = extractNumericData(reversed, props.xAxis);
  const graphLabels = Object.keys(graphDataByMetadataLabel).slice(0, 20).sort();

  const [collapsedLabels, setCollapsedLabels] = useStateWithStorage(
    'hidden-graphs',
    validateHiddenGraphsState,
  );

  const toggleCollapsed = React.useCallback(
    (label: string) => {
      setCollapsedLabels((current = []) =>
        current.includes(label) ? current.filter((c) => c !== label) : [...current, label],
      );
    },
    [setCollapsedLabels],
  );

  return (
    <>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'stretch',
          flexDirection: 'column',
        }}
      >
        {graphLabels.map((label) => (
          <Box
            key={label}
            style={{width: '100%'}}
            border={{side: 'bottom', width: 1, color: ColorsWIP.KeylineGray}}
          >
            {props.asSidebarSection ? (
              <Box padding={{horizontal: 24, top: 8}} flex={{justifyContent: 'space-between'}}>
                <Caption style={{fontWeight: 700}}>{label}</Caption>
                <Checkbox
                  format="switch"
                  checked={!collapsedLabels.includes(label)}
                  onChange={() => toggleCollapsed(label)}
                  size="small"
                />
              </Box>
            ) : (
              <Box
                padding={{horizontal: 24, vertical: 16}}
                border={{side: 'bottom', width: 1, color: ColorsWIP.KeylineGray}}
                flex={{justifyContent: 'space-between'}}
              >
                <Subheading>{label}</Subheading>
                <Checkbox
                  format="switch"
                  checked={!collapsedLabels.includes(label)}
                  onChange={() => toggleCollapsed(label)}
                  size="small"
                />
              </Box>
            )}
            {!collapsedLabels.includes(label) ? (
              <Box padding={{horizontal: 24, vertical: 16}}>
                <AssetValueGraph
                  label={label}
                  width="100%"
                  data={graphDataByMetadataLabel[label]}
                  xHover={xHover}
                  onHoverX={(x) => x !== xHover && setXHover(x)}
                />
              </Box>
            ) : undefined}
          </Box>
        ))}
      </div>
      {graphLabels.length === 0 ? (
        <Box padding={{horizontal: 24, top: 64}}>
          <NonIdealState
            shrinkable
            icon="linear_scale"
            title="No numeric metadata"
            description={`Include numeric metadata entries in your materializations and observations to see data graphed by ${props.xAxis}.`}
          />
        </Box>
      ) : (
        props.xAxis === 'partition' && (
          <Box padding={{vertical: 16, horizontal: 24}} style={{color: ColorsWIP.Gray400}}>
            When graphing values by partition, the highest data point for each materialized event
            label is displayed.
          </Box>
        )
      )}
    </>
  );
};

/**
 * Helper function that iterates over the asset materializations and assembles time series data
 * and stats for all numeric metadata entries. This function makes the following guaruntees:
 *
 * - If a metadata entry is sparsely emitted, points are still included for missing x values
 *   with y = NaN. (For compatiblity with react-chartjs-2)
 * - If a metadata entry is generated many times for the same partition, and xAxis = partition,
 *   the MAX value emitted is used as the data point.
 *
 * Assumes that the data is pre-sorted in ascending partition order if using xAxis = partition.
 */
const extractNumericData = (datapoints: AssetEventGroup[], xAxis: 'time' | 'partition') => {
  const series: {
    [metadataEntryLabel: string]: AssetValueGraphData;
  } = {};

  // Build a set of the numeric metadata entry labels (note they may be sparsely emitted)
  const numericMetadataLabels = uniq(
    flatMap(datapoints, (e) =>
      (e.latest?.metadataEntries || [])
        .filter((k) => ['IntMetadataEntry', 'FloatMetadataEntry'].includes(k.__typename))
        .map((k) => k.label),
    ),
  );

  const append = (label: string, {x, y}: {x: number | string; y: number}) => {
    series[label] = series[label] || {minX: 0, maxX: 0, minY: 0, maxY: 0, values: [], xAxis};

    if (xAxis === 'partition') {
      // If the xAxis is partition keys, the graph may only contain one value for each partition.
      // If the existing sample for the partition was null, replace it. Otherwise take the
      // most recent value.
      const existingForPartition = series[label].values.find((v) => v.x === x);
      if (existingForPartition) {
        if (!isNaN(y)) {
          existingForPartition.y = y;
        }
        return;
      }
    }
    series[label].values.push({
      xNumeric: typeof x === 'number' ? x : series[label].values.length,
      x,
      y,
    });
  };

  for (const {partition, latest} of datapoints) {
    const x = (xAxis === 'partition' ? partition : Number(latest?.timestamp)) || null;

    if (x === null) {
      // exclude materializations where partition = null from partitioned graphs
      continue;
    }

    // Add an entry for every numeric metadata label
    for (const label of numericMetadataLabels) {
      const entry = latest?.metadataEntries.find((l) => l.label === label);
      if (!entry) {
        append(label, {x, y: NaN});
        continue;
      }

      let y = NaN;
      if (entry.__typename === 'IntMetadataEntry') {
        if (entry.intValue !== null) {
          y = entry.intValue;
        } else {
          // will incur precision loss here
          y = parseInt(entry.intRepr);
        }
      }
      if (entry.__typename === 'FloatMetadataEntry' && entry.floatValue !== null) {
        y = entry.floatValue;
      }

      append(label, {x, y});
    }
  }

  for (const serie of Object.values(series)) {
    const xs = serie.values.map((v) => v.xNumeric);
    const ys = serie.values.map((v) => v.y).filter((v) => !isNaN(v));
    serie.minXNumeric = Math.min(...xs);
    serie.maxXNumeric = Math.max(...xs);
    serie.minY = Math.min(...ys);
    serie.maxY = Math.max(...ys);
  }
  return series;
};

const ASSET_EVENTS_QUERY = gql`
  query AssetEventsQuery(
    $assetKey: AssetKeyInput!
    $limit: Int
    $before: String
    $partitionInLast: Int
  ) {
    assetOrError(assetKey: $assetKey) {
      ... on Asset {
        id
        key {
          path
        }
        assetObservations(
          limit: $limit
          beforeTimestampMillis: $before
          partitionInLast: $partitionInLast
        ) {
          ...AssetObservationFragment
        }
        assetMaterializations(
          limit: $limit
          beforeTimestampMillis: $before
          partitionInLast: $partitionInLast
        ) {
          ...AssetMaterializationFragment
        }

        definition {
          id
          partitionKeys
        }
      }
    }
  }
  fragment AssetMaterializationFragment on MaterializationEvent {
    partition
    runOrError {
      ... on PipelineRun {
        id
        runId
        mode
        repositoryOrigin {
          id
          repositoryName
          repositoryLocationName
        }
        status
        pipelineName
        pipelineSnapshotId
      }
    }
    runId
    timestamp
    stepKey
    label
    description
    metadataEntries {
      ...MetadataEntryFragment
    }
    assetLineage {
      ...AssetLineageFragment
    }
  }
  fragment AssetObservationFragment on ObservationEvent {
    partition
    runOrError {
      ... on PipelineRun {
        id
        runId
        mode
        repositoryOrigin {
          id
          repositoryName
          repositoryLocationName
        }
        status
        pipelineName
        pipelineSnapshotId
      }
    }
    runId
    timestamp
    stepKey
    stepStats {
      endTime
      startTime
    }
    label
    description
    metadataEntries {
      ...MetadataEntryFragment
    }
  }
  ${METADATA_ENTRY_FRAGMENT}
  ${ASSET_LINEAGE_FRAGMENT}
`;

export const LAST_RUNS_QUERY = gql`
  query LastRunQuery($repositorySelector: RepositorySelector!) {
    repositoryOrError(repositorySelector: $repositorySelector) {
      ... on Repository {
        id
        latestRunByStep {
          __typename
          ... on LatestRun {
            stepKey
            run {
              id
              status
            }
          }
          ... on JobRunsCount {
            stepKey
            jobNames
            count
            sinceLatestMaterialization
          }
        }
      }
    }
  }
`;
