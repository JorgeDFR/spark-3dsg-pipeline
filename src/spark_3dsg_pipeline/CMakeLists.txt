cmake_minimum_required(VERSION 3.16)
project(spark_3dsg_pipeline)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch config rviz DESTINATION share/${PROJECT_NAME})

ament_package()
