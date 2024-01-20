import pandas as pd


def load_and_prepare_data():
    """
    Loads and prepares the performance analysis data from a CSV file.

    Returns:
        df (pandas.DataFrame): The prepared dataframe containing the performance analysis data.
        total_runtime (float): The total runtime of the performance analysis data in seconds.
    """
    df = pd.read_csv("performance_analysis.csv")
    df.columns = [
        "timestamp",
        "num_runs",
        "faster_method",
        "original_time",
        "optimized_time",
        "percent_faster",
    ]
    df.drop("num_runs", axis=1, inplace=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    total_runtime = (
        df["timestamp"].max() - df["timestamp"].min()
    ).total_seconds()
    df.drop("timestamp", axis=1, inplace=True)
    # drop any rows which are significantly outliers (where either the original or optimized time is more than 3 standard deviations from the mean)
    df = df[
        (df["optimized_time"] - df["optimized_time"].mean()).abs()
        <= 3 * df["optimized_time"].std()
    ]
    df = df[
        (df["original_time"] - df["original_time"].mean()).abs()
        <= 3 * df["original_time"].std()
    ]
    # Convert seconds to milliseconds
    df["original_time"] = pd.to_numeric(df["original_time"]) * 1000
    df["optimized_time"] = pd.to_numeric(df["optimized_time"]) * 1000
    # Convert percent to float
    df["percent_faster"] = pd.to_numeric(df["percent_faster"].str.strip("%"))

    return df, total_runtime


def calculate_statistics(df):
    """
    Calculate various statistics based on the given DataFrame.

    Parameters:
    df (pandas.DataFrame): The DataFrame containing the performance data.

    Returns:
    dict: A dictionary containing the calculated statistics.
    """

    stats = {
        # Count the number of times the optimized method was faster
        "optimized_faster_count": df[df["faster_method"] == "Optimized"].shape[
            0
        ],
        # Calculate the total time saved when the optimized method was faster
        "optimized_time_saved": round(
            df[df["faster_method"] == "Optimized"]["original_time"].sum()
            - df[df["faster_method"] == "Optimized"]["optimized_time"].sum(),
            2,
        ),
        # Calculate the average percentage faster when the optimized method was faster
        "average_percent_faster_optimized": round(
            (
                (
                    df[df["faster_method"] == "Optimized"]["original_time"]
                    - df[df["faster_method"] == "Optimized"]["optimized_time"]
                )
                / df[df["faster_method"] == "Optimized"]["original_time"]
                * 100
            ).mean(),
            2,
        ),
        # Count the number of times the original method was faster
        "original_faster_count": df[df["faster_method"] == "Original"].shape[
            0
        ],
        # Calculate the total time lost when the original method was faster
        "original_time_lost": round(
            df[df["faster_method"] == "Original"]["optimized_time"].sum()
            - df[df["faster_method"] == "Original"]["original_time"].sum(),
            2,
        ),
        # Calculate the average percentage slower when the original method was faster
        "average_percent_slower_original": round(
            (
                (
                    df[df["faster_method"] == "Original"]["optimized_time"]
                    - df[df["faster_method"] == "Original"]["original_time"]
                )
                / df[df["faster_method"] == "Original"]["original_time"]
                * 100
            ).mean(),
            2,
        ),
        # Maximum and Minimum Time Saved/Lost
        "max_time_saved": round(
            df[df["faster_method"] == "Optimized"]["original_time"].max()
            - df[df["faster_method"] == "Optimized"]["optimized_time"].max(),
            2,
        ),
        "min_time_saved": round(
            df[df["faster_method"] == "Optimized"]["original_time"].min()
            - df[df["faster_method"] == "Optimized"]["optimized_time"].min(),
            2,
        ),
        "max_time_lost": round(
            df[df["faster_method"] == "Original"]["optimized_time"].max()
            - df[df["faster_method"] == "Original"]["original_time"].max(),
            2,
        ),
        "min_time_lost": round(
            df[df["faster_method"] == "Original"]["optimized_time"].min()
            - df[df["faster_method"] == "Original"]["original_time"].min(),
            2,
        ),
        # Maximum and Minimum Percentage Improvement/Degradation
        "max_percent_improvement": round(
            df[df["faster_method"] == "Optimized"]["percent_faster"].max(), 2
        ),
        "min_percent_improvement": round(
            df[df["faster_method"] == "Optimized"]["percent_faster"].min(), 2
        ),
        "max_percent_degradation": round(
            df[df["faster_method"] == "Original"]["percent_faster"].max(), 2
        ),
        "min_percent_degradation": round(
            df[df["faster_method"] == "Original"]["percent_faster"].min(), 2
        ),
        # Median Time Saved/Lost
        "median_time_saved": round(
            df[df["faster_method"] == "Optimized"]["original_time"].median()
            - df[df["faster_method"] == "Optimized"][
                "optimized_time"
            ].median(),
            2,
        ),
        "median_time_lost": round(
            df[df["faster_method"] == "Original"]["optimized_time"].median()
            - df[df["faster_method"] == "Original"]["original_time"].median(),
            2,
        ),
        # Median Percentage Improvement/Degradation
        "median_percent_improvement": round(
            df[df["faster_method"] == "Optimized"]["percent_faster"].median(),
            2,
        ),
        "median_percent_degradation": round(
            df[df["faster_method"] == "Original"]["percent_faster"].median(), 2
        ),
        # Standard Deviation of Time and Percentage
        "std_dev_time_saved": round(
            (
                df[df["faster_method"] == "Optimized"]["original_time"]
                - df[df["faster_method"] == "Optimized"]["optimized_time"]
            ).std(),
            2,
        ),
        "std_dev_time_lost": round(
            (
                df[df["faster_method"] == "Original"]["optimized_time"]
                - df[df["faster_method"] == "Original"]["original_time"]
            ).std(),
            2,
        ),
        "std_dev_percent_improvement": round(
            (
                (
                    df[df["faster_method"] == "Optimized"]["original_time"]
                    - df[df["faster_method"] == "Optimized"]["optimized_time"]
                )
                / df[df["faster_method"] == "Optimized"]["original_time"]
                * 100
            ).std(),
            2,
        ),
        "std_dev_percent_degradation": round(
            (
                (
                    df[df["faster_method"] == "Original"]["optimized_time"]
                    - df[df["faster_method"] == "Original"]["original_time"]
                )
                / df[df["faster_method"] == "Original"]["original_time"]
                * 100
            ).std(),
            2,
        ),
    }
    return stats


def print_statistics(stats, total_runtime):
    """
    Prints the performance statistics based on the provided data.

    Args:
        stats (dict): A dictionary containing the performance statistics.
        total_runtime (float): The total runtime of the program in seconds.
    """
    print("Performance Analysis\n")

    # Count and Time Analysis
    print("Count and Time Analysis:")
    print(f"Profiled for {total_runtime} seconds.")
    print(
        f"Optimized method was faster {stats['optimized_faster_count']} times, saving {stats['optimized_time_saved']} milliseconds."
    )
    print(
        f"Original method was faster {stats['original_faster_count']} times, causing a total loss of {stats['original_time_lost']} milliseconds.\n"
    )
    # Runtime analysis
    print("Runtime Analysis:")
    print(
        f"Total Runtime savings: {stats['optimized_time_saved'] - stats['original_time_lost']} milliseconds."
    )
    print(
        f"Decreased runtime by {round((stats['optimized_time_saved'] - stats['original_time_lost']) / (total_runtime * 1000) * 100, 2)}%.\n"
    )
    # Average Percentage Analysis
    print("Average Percentage Analysis:")
    print(
        f"When the optimized method was faster, it was on average {stats['average_percent_faster_optimized']}% faster than the original."
    )
    print(
        f"When the original method was faster, the optimized function was on average {stats['average_percent_slower_original']}% slower.\n"
    )

    # Maximum and Minimum Time Saved/Lost Analysis
    print("Maximum and Minimum Time Saved/Lost Analysis:")
    print(
        f"Maximum time saved when optimized method was faster: {stats['max_time_saved']} milliseconds."
    )
    print(
        f"Minimum time saved when optimized method was faster: {stats['min_time_saved']} milliseconds."
    )
    print(
        f"Maximum time lost when original method was faster: {stats['max_time_lost']} milliseconds."
    )
    print(
        f"Minimum time lost when original method was faster: {stats['min_time_lost']} milliseconds.\n"
    )

    # Maximum and Minimum Percentage Improvement/Degradation Analysis
    print("Maximum and Minimum Percentage Improvement/Degradation Analysis:")
    print(
        f"Maximum percentage improvement when optimized method was faster: {stats['max_percent_improvement']}%."
    )
    print(
        f"Minimum percentage improvement when optimized method was faster: {stats['min_percent_improvement']}%."
    )
    print(
        f"Maximum percentage degradation when original method was faster: {stats['max_percent_degradation']}%."
    )
    print(
        f"Minimum percentage degradation when original method was faster: {stats['min_percent_degradation']}%.\n"
    )

    # Median Time Saved/Lost Analysis
    print("Median Time Saved/Lost Analysis:")
    print(
        f"Median time saved when optimized method was faster: {stats['median_time_saved']} milliseconds."
    )
    print(
        f"Median time lost when original method was faster: {stats['median_time_lost']} milliseconds.\n"
    )

    # Median Percentage Improvement/Degradation Analysis
    print("Median Percentage Improvement/Degradation Analysis:")
    print(
        f"Median percentage improvement when optimized method was faster: {stats['median_percent_improvement']}%."
    )
    print(
        f"Median percentage degradation when original method was faster: {stats['median_percent_degradation']}%.\n"
    )

    # Standard Deviation of Time and Percentage Analysis
    print("Standard Deviation of Time and Percentage Analysis:")
    print(
        f"Standard deviation of time saved when optimized method was faster: {stats['std_dev_time_saved']} milliseconds."
    )
    print(
        f"Standard deviation of time lost when original method was faster: {stats['std_dev_time_lost']} milliseconds."
    )
    print(
        f"Standard deviation of percentage improvement when optimized method was faster: {stats['std_dev_percent_improvement']}%."
    )
    print(
        f"Standard deviation of percentage degradation when original method was faster: {stats['std_dev_percent_degradation']}%.\n"
    )

    print("Summary:")
    if stats["optimized_faster_count"] > stats[
        "original_faster_count"
    ] and stats["optimized_time_saved"] > abs(stats["original_time_lost"]):
        speedup = total_runtime / (
            total_runtime - stats["optimized_time_saved"] / 1000
        )
        speedup_percent = round((speedup - 1) * 100, 2)
        print(
            f"The optimized method is the best to use. It was faster more often and saved more total time. Approximate speedup: {speedup_percent}%."
        )
    elif (
        stats["original_faster_count"] > stats["optimized_faster_count"]
        and abs(stats["original_time_lost"]) > stats["optimized_time_saved"]
    ):
        slowdown = total_runtime / (
            total_runtime + stats["original_time_lost"] / 1000
        )
        slowdown_percent = round((1 - slowdown) * 100, 2)
        print(
            f"The original method is the best to use. It was faster more often and lost less total time. Approximate slowdown: {slowdown_percent}%."
        )
    else:
        print(
            "It's not clear which method is better. The performance depends on the specific use case."
        )
    with open("performance_insights.txt", "w") as f:
        f.write("Performance Analysis\n\n")
        f.write("Count and Time Analysis:\n")
        f.write(f"Profiled for {total_runtime} seconds.\n")
        f.write(
            f"Optimized method was faster {stats['optimized_faster_count']} times, saving {stats['optimized_time_saved']} milliseconds.\n"
        )
        f.write(
            f"Original method was faster {stats['original_faster_count']} times, losing {stats['original_time_lost']} milliseconds.\n\n"
        )
        f.write("Runtime Analysis:\n")
        f.write(
            f"Total Runtime savings: {stats['optimized_time_saved'] - stats['original_time_lost']} milliseconds.\n"
        )
        f.write(
            f"Decreased runtime by {round((stats['optimized_time_saved'] - stats['original_time_lost']) / (total_runtime * 1000) * 100, 2)}%.\n\n"
        )
        f.write("Average Percentage Analysis:\n")
        f.write(
            f"When the optimized method was faster, it was on average {stats['average_percent_faster_optimized']}% faster than the original.\n"
        )
        f.write(
            f"When the original method was faster, the optimized function was on average {stats['average_percent_slower_original']}% slower.\n\n"
        )
        f.write("Maximum and Minimum Time Saved/Lost Analysis:\n")
        f.write(
            f"Maximum time saved when optimized method was faster: {stats['max_time_saved']} milliseconds.\n"
        )
        f.write(
            f"Minimum time saved when optimized method was faster: {stats['min_time_saved']} milliseconds.\n"
        )
        f.write(
            f"Maximum time lost when original method was faster: {stats['max_time_lost']} milliseconds.\n"
        )
        f.write(
            f"Minimum time lost when original method was faster: {stats['min_time_lost']} milliseconds.\n\n"
        )
        f.write(
            "Maximum and Minimum Percentage Improvement/Degradation Analysis:\n"
        )
        f.write(
            f"Maximum percentage improvement when optimized method was faster: {stats['max_percent_improvement']}%.\n"
        )
        f.write(
            f"Minimum percentage improvement when optimized method was faster: {stats['min_percent_improvement']}%.\n"
        )
        f.write(
            f"Maximum percentage degradation when original method was faster: {stats['max_percent_degradation']}%.\n"
        )
        f.write(
            f"Minimum percentage degradation when original method was faster: {stats['min_percent_degradation']}%.\n\n"
        )
        f.write("Median Time Saved/Lost Analysis:\n")
        f.write(
            f"Median time saved when optimized method was faster: {stats['median_time_saved']} milliseconds.\n"
        )
        f.write(
            f"Median time lost when original method was faster: {stats['median_time_lost']} milliseconds.\n\n"
        )
        f.write("Median Percentage Improvement/Degradation Analysis:\n")
        f.write(
            f"Median percentage improvement when optimized method was faster: {stats['median_percent_improvement']}%.\n"
        )
        f.write(
            f"Median percentage degradation when original method was faster: {stats['median_percent_degradation']}%.\n\n"
        )
        f.write("Standard Deviation of Time and Percentage Analysis:\n")
        f.write(
            f"Standard deviation of time saved when optimized method was faster: {stats['std_dev_time_saved']} milliseconds.\n"
        )
        f.write(
            f"Standard deviation of time lost when original method was faster: {stats['std_dev_time_lost']} milliseconds.\n"
        )
        f.write(
            f"Standard deviation of percentage improvement when optimized method was faster: {stats['std_dev_percent_improvement']}%.\n"
        )
        f.write(
            f"Standard deviation of percentage degradation when original method was faster: {stats['std_dev_percent_degradation']}%.\n\n"
        )
        f.write("Summary:\n")
        if stats["optimized_faster_count"] > stats[
            "original_faster_count"
        ] and stats["optimized_time_saved"] > abs(stats["original_time_lost"]):
            speedup = total_runtime / (
                total_runtime - stats["optimized_time_saved"] / 1000
            )
            speedup_percent = round((speedup - 1) * 100, 2)
            f.write(
                f"The optimized method is the best to use. It was faster more often and saved more total time. Approximate speedup: {speedup_percent}%.\n"
            )
        elif (
            stats["original_faster_count"] > stats["optimized_faster_count"]
            and abs(stats["original_time_lost"])
            > stats["optimized_time_saved"]
        ):
            slowdown = total_runtime / (
                total_runtime + stats["original_time_lost"] / 1000
            )
            slowdown_percent = round((1 - slowdown) * 100, 2)
            f.write(
                f"The original method is the best to use. It was faster more often and lost less total time. Approximate slowdown: {slowdown_percent}%.\n"
            )
        else:
            f.write(
                "It's not clear which method is better. The performance depends on the specific use case.\n"
            )


def main():
    """
    This is the main function that loads and prepares data, calculates statistics, and prints the statistics along with the total runtime.
    """
    df, total_runtime = load_and_prepare_data()
    stats = calculate_statistics(df)
    print_statistics(stats, total_runtime)


if __name__ == "__main__":
    main()
