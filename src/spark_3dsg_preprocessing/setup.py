from glob import glob
from pathlib import Path
from setuptools import find_packages, setup


package_name = "spark_3dsg_preprocessing"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*")),
        *[
            (f"share/{package_name}/{directory}", sorted(glob(f"{directory}/*.yaml")))
            for directory in sorted({str(path.parent) for path in Path("config/sources").rglob("*.yaml")})
        ],
        (
            f"share/{package_name}/config/preprocessing",
            glob("config/preprocessing/*.yaml"),
        ),
    ],
    install_requires=["setuptools", "PyYAML"],
    zip_safe=True,
    maintainer="spark-3dsg-pipeline maintainers",
    maintainer_email="maintainers@example.invalid",
    description="RGB-D normalization and upstream odometry backend integration.",
    license="BSD-3-Clause",
    entry_points={
        "console_scripts": [
            "odometry_to_tf = spark_3dsg_preprocessing.odometry_to_tf:main",
            "rgbd_relay = spark_3dsg_preprocessing.rgbd_relay:main",
        ]
    },
)
